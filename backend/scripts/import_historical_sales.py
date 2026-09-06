"""
Convierte inventory_history en Sale + SaleItem para que el dashboard
muestre estadísticas de ventas históricas.

Agrega todas las semanas de cada mes en una sola Sale mensual.
NO modifica Product.stock.

Uso:
    python backend/scripts/import_historical_sales.py [--dry-run]
"""

from __future__ import annotations

import shutil
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select, func
from app.db import SessionLocal, engine
from app.models import Base, InventoryHistory, Product, Sale, SaleItem


def create_backup(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = db_path.parent / f"gato_contable.db.bak-before-historical-sales-{ts}"
    shutil.copy2(db_path, bak)
    if bak.exists() and bak.stat().st_size > 0:
        return bak
    return None


def run_import(dry_run: bool = False) -> dict:
    result = {
        "sales_created": 0,
        "items_created": 0,
        "skipped_existing": 0,
        "months_processed": 0,
        "total_revenue": 0,
    }

    db = SessionLocal()
    try:
        all_records = db.scalars(
            select(InventoryHistory)
            .where(InventoryHistory.units_sold > 0)
            .order_by(InventoryHistory.period_date)
        ).all()

        monthly: dict[str, dict] = defaultdict(lambda: {"items": {}, "date": None})

        for rec in all_records:
            month_key = rec.period_date.strftime("%Y-%m")
            if monthly[month_key]["date"] is None:
                monthly[month_key]["date"] = rec.period_date
            pid = rec.product_id
            if pid not in monthly[month_key]["items"]:
                monthly[month_key]["items"][pid] = {
                    "product_id": pid,
                    "quantity": Decimal("0"),
                    "total": Decimal("0"),
                    "price": rec.sale_price,
                }
            monthly[month_key]["items"][pid]["quantity"] += rec.units_sold
            monthly[month_key]["items"][pid]["total"] += rec.total_sold
            if rec.sale_price > 0:
                monthly[month_key]["items"][pid]["price"] = rec.sale_price

        for month_key in sorted(monthly.keys()):
            data = monthly[month_key]
            items = data["items"]

            month_total = sum(i["total"] for i in items.values())
            if month_total <= 0:
                continue

            sale_number = f"HV-{month_key}"

            existing = db.scalar(
                select(Sale).where(Sale.number == sale_number)
            )
            if existing:
                result["skipped_existing"] += 1
                continue

            result["months_processed"] += 1

            if dry_run:
                result["sales_created"] += 1
                result["items_created"] += len(items)
                result["total_revenue"] += float(month_total)
                continue

            sale = Sale(
                number=sale_number,
                customer_name="Venta histórica",
                payment_method="efectivo",
                total=month_total,
                status="completada",
                created_at=data["date"],
            )
            db.add(sale)
            db.flush()

            for pid, item_data in items.items():
                if item_data["quantity"] <= 0:
                    continue
                sale_item = SaleItem(
                    sale=sale,
                    product_id=item_data["product_id"],
                    quantity=item_data["quantity"],
                    unit_price=item_data["price"],
                )
                db.add(sale_item)
                result["items_created"] += 1

            result["sales_created"] += 1
            result["total_revenue"] += float(month_total)

        if not dry_run:
            db.commit()
        else:
            db.rollback()

    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

    return result


def main():
    dry_run = "--dry-run" in sys.argv

    if not dry_run:
        db_path = BACKEND_DIR / "gato_contable.db"
        bak = create_backup(db_path)
        if bak:
            print(f"Backup: {bak}")

    result = run_import(dry_run=dry_run)

    print(f"\nMeses procesados:    {result['months_processed']}")
    print(f"Ventas creadas:      {result['sales_created']}")
    print(f"Items creados:       {result['items_created']}")
    print(f"Omitidas (existentes): {result['skipped_existing']}")
    print(f"Ingreso total:       ${result['total_revenue']:,.0f}")

    if dry_run:
        print("\nDRY RUN - no se modificó la DB")
    else:
        print("\nImportación completa.")


if __name__ == "__main__":
    main()
