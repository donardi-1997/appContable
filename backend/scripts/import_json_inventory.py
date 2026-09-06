"""
Importador JSON historico de inventario y ventas para La Patrona VIP.

Lee un archivo JSON con hojas mensuales (marzo-agosto 2026) y crea registros
en la tabla inventory_history. Auto-crea productos inexistentes.

Uso:
    python backend/scripts/import_json_inventory.py <ruta_json> [--dry-run] [--strict] [--report]

Reutiliza la logica de import_historical_inventory.py adaptada para JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
APP_DIR = BACKEND_DIR / "app"
sys.path.insert(0, str(BACKEND_DIR))

from app.models import Base, InventoryHistory, Product

SOURCE_TAG = "json_import_2026"

COLUMN_MAP = {
    "LA PATRONA VIP": "product_name",
    "Column3": "opening_stock",
    "Column4": "incoming_stock",
    "Column5": "closing_stock",
    "Column6": "units_sold",
    "Column7": "sale_price",
    "Column8": "total_sold",
    "Column9": "ideal_stock",
    "Column10": "suggested_order",
}

SKIP_KEYWORDS = {
    "TOTAL", "SUBTOTAL", "TOTALES", "SUMA", "GENERAL", "PROMEDIO",
    "GASTOS", "DEUDORES", "DESCUADRE", "BOLETERIA", "CONSIGNACIONES",
}

GASTOS_KEYWORDS = {
    "STAFF", "DJ", "HIELO", "LIMON", "MANI", "ASEO", "PAGO",
    "CERVEZA DA", "BEBIDA", "COPAS", "AGUA MASTER", "ARTISTA",
    "CANTANTE", "MARIACHI", "MESERO", "MESERA", "PAPEL", "GAS",
    "INTERNET", "RECIBO", "RETENCION", "TURNO", "DESCUENTO",
    "ENVASE", "BOLSAS", "TRAPERO", "PINTADA", "CEPILLO",
    "PITA", "RON DEGUSTACION", "ARREGLO", "JUAN SANCHEZ",
    "SENSOR", "PARTIDO", "LUCHY", "manillas", "FERNANDO",
    "LUISA", "ANDRES PARLANTES", "POLA", "ORQUESTA",
    "PAGO APOYO", "PAGO ARTISTA", "PAGO BABARIA", "PAGO STAFF",
    "PAGO PERSONAL", "CERVEZA CONGELADA", "GASTOS DISCOTECA",
    "BASE POLA", "BASE POLA", "IMPRECIONES", "RON RIFA",
    "RECIBOS LUZ", "AGUAS MASTER", "SELLO ROJO DESCUENTO",
}


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_number(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return Decimal("0") if not value else None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, Decimal):
        return value
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    s = re.sub(r"[$\s]", "", s)
    s = re.sub(r"(?<=\d)[.,](?=\d{3}(\D|$))", "", s)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_sheet_date(sheet_name: str) -> datetime | None:
    name = sheet_name.strip().upper()
    month_map = {
        "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
        "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
        "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
        "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
    }

    name_clean = re.sub(r"\s*\(\d+\)\s*$", "", name).strip()

    for month_name, month_num in month_map.items():
        if month_name in name_clean:
            idx = name_clean.index(month_name)
            before = name_clean[:idx].strip()
            after = name_clean[idx + len(month_name):].strip().lstrip("-").strip()

            day = None
            if before:
                nums = re.findall(r"\d+", before)
                if nums:
                    day = int(nums[0])

            year = None
            if after.isdigit() and len(after) == 4:
                year = int(after)
            elif after.isdigit() and len(after) == 2:
                year = 2000 + int(after)

            if year is None:
                year = 2026
            if day is None:
                day = 1

            try:
                return datetime(year, month_num, day)
            except ValueError:
                continue

    match = re.match(r"^(\d{1,2})\s*[-/]\s*(\d{4})$", name)
    if match:
        try:
            return datetime(int(match.group(2)), int(match.group(1)), 1)
        except ValueError:
            pass

    return None


def normalize_product_name(name: str) -> str:
    return " ".join(name.strip().split()).upper()


def is_valid_product_row(row_data: dict) -> bool:
    name = row_data.get("product_name")
    if not name or not isinstance(name, str) or not name.strip():
        return False

    name_upper = name.strip().upper()

    if name_upper in {",", ".", "...", "-"}:
        return False

    for kw in SKIP_KEYWORDS:
        if name_upper.startswith(kw):
            return False

    if name_upper.startswith("BASE"):
        return False

    has_numeric = False
    for key in ("opening_stock", "incoming_stock", "closing_stock", "units_sold"):
        v = row_data.get(key)
        if v is not None and isinstance(v, Decimal) and v != Decimal("0"):
            has_numeric = True
            break
        if v is not None and isinstance(v, Decimal):
            has_numeric = True

    return has_numeric


def is_gastos_row(row_data: dict) -> bool:
    name = row_data.get("product_name", "")
    if not name:
        return False
    name_upper = name.strip().upper()
    for kw in GASTOS_KEYWORDS:
        if kw.upper() in name_upper:
            return True
    return False


@dataclass
class ImportReport:
    source_file: str = ""
    sha256: str = ""
    sheets_total: int = 0
    sheets_processed: int = 0
    sheets_skipped: int = 0
    rows_read: int = 0
    rows_valid: int = 0
    rows_skipped: int = 0
    rows_gastos: int = 0
    rows_deudores: int = 0
    products_found: int = 0
    products_created: int = 0
    products_ambiguous: int = 0
    histories_created: int = 0
    histories_existing: int = 0
    inventory_warnings: int = 0
    total_warnings: int = 0
    errors: int = 0
    validation_errors: int = 0
    stock_updated: int = 0
    ideal_stock_updated: int = 0
    price_updated: int = 0
    warnings: list[dict] = field(default_factory=list)
    errors_list: list[dict] = field(default_factory=list)
    skipped_products: list[str] = field(default_factory=list)
    skipped_sheets: list[str] = field(default_factory=list)
    ambiguous_products: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source_file,
            "sha256": self.sha256,
            "records_read": self.rows_read,
            "products_matched": self.products_found,
            "products_created": self.products_created,
            "records_inserted": self.histories_created,
            "records_updated": 0,
            "records_skipped": self.rows_skipped + self.rows_gastos + self.rows_deudores,
            "duplicates": self.histories_existing,
            "ambiguous_matches": self.products_ambiguous,
            "validation_errors": self.validation_errors,
            "summary": {
                "sheets_total": self.sheets_total,
                "sheets_processed": self.sheets_processed,
                "sheets_skipped": self.sheets_skipped,
                "rows_read": self.rows_read,
                "rows_valid": self.rows_valid,
                "rows_skipped": self.rows_skipped,
                "rows_gastos": self.rows_gastos,
                "rows_deudores": self.rows_deudores,
                "products_found": self.products_found,
                "products_created": self.products_created,
                "products_ambiguous": self.products_ambiguous,
                "histories_created": self.histories_created,
                "histories_existing": self.histories_existing,
                "inventory_warnings": self.inventory_warnings,
                "total_warnings": self.total_warnings,
                "errors": self.errors,
                "validation_errors": self.validation_errors,
                "stock_updated": self.stock_updated,
                "ideal_stock_updated": self.ideal_stock_updated,
                "price_updated": self.price_updated,
            },
            "warnings": self.warnings[:50],
            "errors": self.errors_list,
            "skipped_products": self.skipped_products,
            "skipped_sheets": self.skipped_sheets,
            "ambiguous_products": self.ambiguous_products,
        }


def extract_product_rows(sheet_rows: list[dict]) -> list[dict]:
    product_rows = []
    in_gastos_section = False

    for row in sheet_rows:
        if row is None:
            continue

        name = row.get("product_name")
        if not name:
            continue

        name_upper = name.strip().upper()

        if name_upper == "GASTOS":
            in_gastos_section = True
            continue

        if name_upper in ("DEUDORES", "DESCUADRE", "TOTAL RECIBIDO+DEUDORES"):
            in_gastos_section = True
            continue

        if in_gastos_section:
            continue

        if name_upper == "TOTAL VENTAS":
            continue

        if name_upper in SKIP_KEYWORDS:
            continue

        if name_upper.startswith("BASE"):
            continue

        product_rows.append(row)

    return product_rows


def find_or_create_product(
    db: Session,
    product_name: str,
    report: ImportReport,
    product_cache: dict[str, Product],
) -> Product | None:
    normalized = normalize_product_name(product_name)

    if normalized in product_cache:
        report.products_found += 1
        return product_cache[normalized]

    all_products = db.query(Product).filter(Product.active == True).all()
    for p in all_products:
        p_norm = normalize_product_name(p.name)
        product_cache[p_norm] = p

    if normalized in product_cache:
        report.products_found += 1
        return product_cache[normalized]

    new_product = Product(
        name=product_name.strip(),
        stock=Decimal("0"),
        price=Decimal("0"),
        cost_price=Decimal("0"),
        minimum_stock=Decimal("0"),
        active=True,
    )
    db.add(new_product)
    db.flush()
    product_cache[normalized] = new_product
    report.products_created += 1
    return new_product


def process_sheet(
    db: Session,
    sheet_name: str,
    rows: list[dict],
    report: ImportReport,
    product_cache: dict[str, Product],
) -> list[dict]:
    period_date = parse_sheet_date(sheet_name)
    if period_date is None:
        report.sheets_skipped += 1
        report.skipped_sheets.append(sheet_name)
        report.warnings.append({
            "sheet": sheet_name,
            "message": f"No se pudo interpretar la fecha de la hoja '{sheet_name}'",
        })
        report.total_warnings += 1
        return []

    product_rows = extract_product_rows(rows)
    records: list[dict] = []
    name_occurrence: dict[str, int] = {}

    for row_data in product_rows:
        report.rows_read += 1

        product_name = row_data.get("product_name", "").strip()
        if not product_name:
            report.rows_skipped += 1
            continue

        if not is_valid_product_row(row_data):
            if is_gastos_row(row_data):
                report.rows_gastos += 1
            else:
                report.rows_skipped += 1
            continue

        report.rows_valid += 1

        product = find_or_create_product(db, product_name, report, product_cache)
        if product is None:
            report.products_pending += 1
            report.skipped_products.append(product_name)
            continue

        norm_name = normalize_product_name(product_name)
        name_occurrence[norm_name] = name_occurrence.get(norm_name, 0) + 1
        occurrence = name_occurrence[norm_name]

        if norm_name == "SMIRNOFF" and occurrence > 1:
            product = find_or_create_product(db, "SMIRNOFF MINI", report, product_cache)
            if product is None:
                report.products_pending += 1
                report.skipped_products.append(product_name)
                continue

        source_key = f"{SOURCE_TAG}:{sheet_name}"
        if occurrence > 1:
            source_key = f"{source_key}:#{occurrence}"
        existing = (
            db.query(InventoryHistory)
            .filter(
                InventoryHistory.product_id == product.id,
                InventoryHistory.period_date == period_date,
                InventoryHistory.source == source_key,
            )
            .first()
        )
        if existing:
            report.histories_existing += 1
            continue

        opening_stock = row_data.get("opening_stock") or Decimal("0")
        incoming_stock = row_data.get("incoming_stock") or Decimal("0")
        closing_stock = row_data.get("closing_stock") or Decimal("0")
        units_sold = row_data.get("units_sold") or Decimal("0")
        sale_price = row_data.get("sale_price") or Decimal("0")
        total_sold = row_data.get("total_sold") or Decimal("0")
        ideal_stock_val = row_data.get("ideal_stock")
        suggested_order_val = row_data.get("suggested_order")

        if isinstance(opening_stock, bool):
            opening_stock = Decimal("0")
        if isinstance(closing_stock, bool):
            closing_stock = Decimal("0")
        if isinstance(units_sold, bool):
            units_sold = Decimal("0")
        if isinstance(total_sold, bool):
            total_sold = Decimal("0")

        calculated_sales = opening_stock + incoming_stock - closing_stock
        if calculated_sales != units_sold and units_sold != Decimal("0"):
            diff = abs(calculated_sales - units_sold)
            if diff > Decimal("1"):
                report.inventory_warnings += 1
                report.total_warnings += 1
                report.warnings.append({
                    "sheet": sheet_name,
                    "product": product_name,
                    "message": (
                        f"Venta calculada ({calculated_sales}) != JSON ({units_sold}). "
                        f"Diferencia: {diff}"
                    ),
                })

        calculated_total = units_sold * sale_price if sale_price else Decimal("0")
        if total_sold and calculated_total and total_sold != calculated_total:
            diff = abs(calculated_total - total_sold)
            if diff > Decimal("1"):
                report.total_warnings += 1
                report.warnings.append({
                    "sheet": sheet_name,
                    "product": product_name,
                    "message": (
                        f"Total vendido calculado ({calculated_total}) != JSON ({total_sold}). "
                        f"Diferencia: {diff}"
                    ),
                })

        record = {
            "product_id": product.id,
            "period_date": period_date,
            "opening_stock": opening_stock,
            "incoming_stock": incoming_stock,
            "closing_stock": closing_stock,
            "units_sold": units_sold,
            "sale_price": sale_price,
            "total_sold": total_sold or calculated_total,
            "ideal_stock": ideal_stock_val,
            "suggested_order": suggested_order_val,
            "source": source_key,
            "source_sheet": sheet_name,
        }
        records.append(record)

    return records


def update_product_stock_and_ideal(
    db: Session,
    records: list[dict],
    report: ImportReport,
) -> None:
    if not records:
        return

    product_latest: dict[int, dict] = {}
    product_latest_valid_price: dict[int, tuple[datetime, Decimal]] = {}

    for rec in records:
        pid = rec["product_id"]
        pd = rec["period_date"]
        if pid not in product_latest or pd > product_latest[pid]["period_date"]:
            product_latest[pid] = rec

        sp = rec.get("sale_price")
        if sp and sp > Decimal("0"):
            if pid not in product_latest_valid_price or pd > product_latest_valid_price[pid][0]:
                product_latest_valid_price[pid] = (pd, sp)

    for pid, rec in product_latest.items():
        product = db.query(Product).filter(Product.id == pid).first()
        if not product:
            continue

        new_stock = rec["closing_stock"]
        if product.stock != new_stock:
            product.stock = new_stock
            report.stock_updated += 1

        if rec["ideal_stock"] is not None:
            if product.ideal_stock != rec["ideal_stock"]:
                product.ideal_stock = rec["ideal_stock"]
                report.ideal_stock_updated += 1

        if product.price == Decimal("0") and pid in product_latest_valid_price:
            valid_price = product_latest_valid_price[pid][1]
            if valid_price > Decimal("0"):
                product.price = valid_price
                report.price_updated += 1


def create_backup(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.parent / f"gato_contable.db.bak-before-json-import-{timestamp}"
    shutil.copy2(db_path, backup_path)

    if backup_path.exists() and backup_path.stat().st_size > 0:
        import sqlite3
        try:
            conn = sqlite3.connect(str(backup_path))
            conn.execute("PRAGMA integrity_check")
            conn.close()
            return backup_path
        except Exception:
            return None
    return None


def run_import(
    filepath: Path,
    dry_run: bool = False,
    strict: bool = False,
    db_engine: Any = None,
    session_factory: Any = None,
) -> ImportReport:
    from app.db import SessionLocal as _SessionLocal, engine as _engine

    if db_engine is None:
        db_engine = _engine
    if session_factory is None:
        session_factory = _SessionLocal

    report = ImportReport()
    report.source_file = str(filepath.name)
    report.sha256 = sha256_file(filepath)

    if not filepath.exists():
        report.errors += 1
        report.errors_list.append({"message": f"Archivo no encontrado: {filepath}"})
        return report

    print(f"Leyendo JSON: {filepath}")
    print(f"SHA-256: {report.sha256}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        report.errors += 1
        report.errors_list.append({"message": "El JSON raiz debe ser un objeto (dict)"})
        return report

    sheet_names = list(data.keys())
    report.sheets_total = len(sheet_names)
    print(f"Hojas encontradas: {len(sheet_names)}")

    Base.metadata.create_all(bind=db_engine)

    product_cache: dict[str, Product] = {}
    all_records: list[dict] = []

    db = session_factory()
    try:
        for sheet_name in sheet_names:
            if sheet_name.strip().upper() == "DESCUADRES":
                print(f"  Omitiendo hoja DESCUADRES (estructura diferente)")
                report.sheets_skipped += 1
                report.skipped_sheets.append(sheet_name)
                continue

            period_date = parse_sheet_date(sheet_name)
            if period_date is None:
                report.sheets_skipped += 1
                report.skipped_sheets.append(sheet_name)
                report.warnings.append({
                    "sheet": sheet_name,
                    "message": f"No se pudo interpretar la fecha de la hoja '{sheet_name}'",
                })
                report.total_warnings += 1
                print(f"  Omitiendo '{sheet_name}': sin fecha interpretable")
                continue

            sheet_rows = data[sheet_name]
            if not isinstance(sheet_rows, list):
                report.sheets_skipped += 1
                continue

            parsed_rows: list[dict] = []
            for raw_row in sheet_rows:
                if raw_row is None:
                    parsed_rows.append(None)
                    continue
                if not isinstance(raw_row, dict):
                    parsed_rows.append(None)
                    continue

                row_data: dict[str, Any] = {}
                for json_key, field_name in COLUMN_MAP.items():
                    val = raw_row.get(json_key)
                    if field_name == "product_name":
                        row_data[field_name] = str(val).strip() if val is not None else ""
                    else:
                        row_data[field_name] = parse_number(val)
                parsed_rows.append(row_data)

            print(f"  Procesando '{sheet_name}' ({period_date.strftime('%Y-%m-%d')})")
            records = process_sheet(db, sheet_name, parsed_rows, report, product_cache)
            all_records.extend(records)
            report.sheets_processed += 1

        for rec in all_records:
            if not dry_run:
                history = InventoryHistory(**rec)
                db.add(history)
            report.histories_created += 1

        if not dry_run:
            update_product_stock_and_ideal(db, all_records, report)

        if not dry_run:
            db.commit()
            print("\nCommit exitoso.")
        else:
            db.rollback()
            print("\nDRY RUN - rollback ejecutado, DB no modificada.")

    except Exception as e:
        db.rollback()
        report.errors += 1
        report.errors_list.append({"message": f"Error critico: {e}"})
        print(f"\nERROR CRITICO: {e}")
        print("Rollback ejecutado.")
    finally:
        db.close()

    return report


def print_report(report: ImportReport, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "COMMIT"
    sep = "=" * 60

    print(f"\n{sep}")
    print("LA PATRONA VIP - IMPORTACION JSON HISTORICA")
    print(sep)
    print(f"Archivo:               {report.source_file}")
    print(f"SHA-256:               {report.sha256[:32]}...")
    print(f"Hojas totales:         {report.sheets_total}")
    print(f"Hojas procesadas:      {report.sheets_processed}")
    print(f"Hojas omitidas:        {report.sheets_skipped}")
    print(f"Filas leidas:          {report.rows_read}")
    print(f"Filas validas:         {report.rows_valid}")
    print(f"Filas omitidas:        {report.rows_skipped}")
    print(f"Filas gastos:          {report.rows_gastos}")
    print(f"Filas deudores:        {report.rows_deudores}")
    print(f"Productos encontrados: {report.products_found}")
    print(f"Productos creados:     {report.products_created}")
    print(f"Productos ambiguos:    {report.products_ambiguous}")
    print(f"Historicos creados:    {report.histories_created}")
    print(f"Historicos existentes: {report.histories_existing}")
    print(f"Advertencias inv.:     {report.inventory_warnings}")
    print(f"Advertencias totales:  {report.total_warnings}")
    print(f"Errores validacion:    {report.validation_errors}")
    print(f"Errores:               {report.errors}")
    print(f"Stock actualizado:     {report.stock_updated}")
    print(f"Stock ideal actual.:   {report.ideal_stock_updated}")
    print(f"Precio actualizado:    {report.price_updated}")
    print(f"\nModo: {mode}")
    print(sep)

    if report.warnings:
        print(f"\nAdvertencias ({len(report.warnings)}):")
        for w in report.warnings[:20]:
            print(f"  [{w.get('sheet','')}] {w.get('product','')} - {w.get('message','')}")
        if len(report.warnings) > 20:
            print(f"  ... y {len(report.warnings) - 20} mas")

    if report.errors_list:
        print(f"\nErrores ({len(report.errors_list)}):")
        for e in report.errors_list:
            print(f"  {e.get('message','')}")

    if report.skipped_sheets:
        print(f"\nHojas omitidas: {report.skipped_sheets}")


def main():
    parser = argparse.ArgumentParser(
        description="Importa historico de inventario desde JSON para La Patrona VIP."
    )
    parser.add_argument("filepath", type=str, help="Ruta al archivo JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin modificar DB.")
    parser.add_argument("--strict", action="store_true", help="Modo estricto: abortar en errores.")
    parser.add_argument("--report", type=str, help="Ruta para guardar reporte JSON.")
    args = parser.parse_args()

    filepath = Path(args.filepath)

    if not args.dry_run:
        db_path = BACKEND_DIR / "gato_contable.db"
        backup_path = create_backup(db_path)
        if backup_path:
            print(f"Backup creado: {backup_path}")
        else:
            print("ADVERTENCIA: No se pudo crear backup.")

    report = run_import(filepath, dry_run=args.dry_run, strict=args.strict)
    print_report(report, dry_run=args.dry_run)

    report_path = Path(args.report) if args.report else filepath.parent / "json_import_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReporte guardado: {report_path}")


if __name__ == "__main__":
    main()
