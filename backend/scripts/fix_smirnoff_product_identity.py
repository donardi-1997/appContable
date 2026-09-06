"""
Separa SMIRNOFF en dos Products: botella (95000) y presentación pequeña (10000).

Regla determinística: en cada hoja, la PRIMERA aparición de "SMIRNOFF" es la
serie HIGH_PRICE (95000) y la SEGUNDA es la serie LOW_PRICE (10000).
Esto se refleja en el source key: sin sufijo vs :#2.

Uso:
    python backend/scripts/fix_smirnoff_product_identity.py [--dry-run]
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from app.db import SessionLocal, engine
from app.models import Base, InventoryHistory, Product

SMIRNOFF_NAME = "SMIRNOFF"
SMIRNOFF_MINI_NAME = "SMIRNOFF MINI"
HIGH_PRICE = Decimal("95000")
LOW_PRICE = Decimal("10000")
HIGH_IDEAL = Decimal("6")
LOW_IDEAL = Decimal("24")
SOURCE_SUFFIX = ":#2"


def create_backup(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = db_path.parent / f"gato_contable.db.bak-before-smirnoff-fix-{ts}"
    shutil.copy2(db_path, bak)
    if bak.exists() and bak.stat().st_size > 0:
        conn = sqlite3.connect(str(bak))
        conn.execute("PRAGMA integrity_check")
        conn.close()
        return bak
    return None


def find_smirnoff_product(db) -> Product | None:
    products = db.query(Product).filter(Product.active == True).all()
    for p in products:
        if p.name.strip().upper() == SMIRNOFF_NAME:
            return p
    return None


def find_smirnoff_mini_product(db) -> Product | None:
    products = db.query(Product).filter(Product.active == True).all()
    for p in products:
        if p.name.strip().upper() == SMIRNOFF_MINI_NAME:
            return p
    return None


def classify_histories(db, product_id: int) -> dict:
    all_hist = (
        db.query(InventoryHistory)
        .filter(InventoryHistory.product_id == product_id)
        .all()
    )

    high = []
    low = []
    ambiguous = []

    for h in all_hist:
        src = h.source or ""
        if SOURCE_SUFFIX in src:
            low.append(h)
        else:
            high.append(h)

    return {
        "high": high,
        "low": low,
        "ambiguous": ambiguous,
        "total": len(all_hist),
    }


def get_latest_valid(histories: list, field: str) -> Decimal | None:
    sorted_h = sorted(histories, key=lambda h: h.period_date, reverse=True)
    for h in sorted_h:
        val = getattr(h, field)
        if val is not None and val > Decimal("0"):
            return val
    return None


def run_fix(dry_run: bool = False) -> dict:
    result = {
        "already_fixed": False,
        "smirnoff_id": None,
        "smirnoff_mini_id": None,
        "high_count": 0,
        "low_count": 0,
        "high_price": float(HIGH_PRICE),
        "low_price": float(LOW_PRICE),
        "high_stock": 0,
        "low_stock": 0,
        "high_ideal": float(HIGH_IDEAL),
        "low_ideal": float(LOW_IDEAL),
        "products_before": 0,
        "products_after": 0,
        "history_total": 0,
    }

    db = SessionLocal()
    try:
        result["products_before"] = db.query(Product).count()
        result["history_total"] = db.query(InventoryHistory).count()

        smirnoff = find_smirnoff_product(db)
        if not smirnoff:
            result["error"] = "Product SMIRNOFF not found"
            return result

        result["smirnoff_id"] = smirnoff.id

        mini = find_smirnoff_mini_product(db)
        if mini:
            result["already_fixed"] = True
            result["smirnoff_mini_id"] = mini.id

            classified = classify_histories(db, smirnoff.id)
            result["high_count"] = len(classified["high"])

            mini_hist = (
                db.query(InventoryHistory)
                .filter(InventoryHistory.product_id == mini.id)
                .count()
            )
            result["low_count"] = mini_hist

            print(f"ALREADY_FIXED: SMIRNOFF(id={smirnoff.id}) + SMIRNOFF MINI(id={mini.id})")
            print(f"  HIGH series: {result['high_count']} records")
            print(f"  LOW series:  {result['low_count']} records")
            return result

        classified = classify_histories(db, smirnoff.id)
        high_records = classified["high"]
        low_records = classified["low"]
        result["high_count"] = len(high_records)
        result["low_count"] = len(low_records)

        high_stock = get_latest_valid(high_records, "closing_stock") or Decimal("0")
        low_stock = get_latest_valid(low_records, "closing_stock") or Decimal("0")
        result["high_stock"] = float(high_stock)
        result["low_stock"] = float(low_stock)

        print(f"SMIRNOFF separation plan:")
        print(f"  Product to KEEP as SMIRNOFF: id={smirnoff.id}")
        print(f"    HIGH series records: {len(high_records)}")
        print(f"    price: {smirnoff.price} -> {HIGH_PRICE}")
        print(f"    stock: {smirnoff.stock} -> {high_stock}")
        print(f"    ideal_stock: {smirnoff.ideal_stock} -> {HIGH_IDEAL}")
        print(f"  Product to CREATE as SMIRNOFF MINI:")
        print(f"    LOW series records to reassign: {len(low_records)}")
        print(f"    price: {LOW_PRICE}")
        print(f"    stock: {low_stock}")
        print(f"    ideal_stock: {LOW_IDEAL}")

        if dry_run:
            print("\nDRY RUN - no changes made")
            return result

        new_product = Product(
            name=SMIRNOFF_MINI_NAME,
            stock=low_stock,
            price=LOW_PRICE,
            cost_price=Decimal("0"),
            minimum_stock=Decimal("0"),
            ideal_stock=LOW_IDEAL,
            active=True,
            tax_rate=smirnoff.tax_rate,
            tax_type=smirnoff.tax_type,
        )
        db.add(new_product)
        db.flush()

        result["smirnoff_mini_id"] = new_product.id

        for h in low_records:
            h.product_id = new_product.id

        smirnoff.price = HIGH_PRICE
        smirnoff.stock = high_stock
        smirnoff.ideal_stock = HIGH_IDEAL

        db.commit()

        result["products_after"] = db.query(Product).count()
        print(f"\nFix applied successfully.")
        print(f"  SMIRNOFF (id={smirnoff.id}): price={HIGH_PRICE}, stock={high_stock}, ideal={HIGH_IDEAL}")
        print(f"  SMIRNOFF MINI (id={new_product.id}): price={LOW_PRICE}, stock={low_stock}, ideal={LOW_IDEAL}")
        print(f"  Records reassigned: {len(low_records)}")
        print(f"  Products: {result['products_before']} -> {result['products_after']}")

    except Exception as e:
        db.rollback()
        result["error"] = str(e)
        print(f"ERROR: {e}")
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
        else:
            print("WARNING: Could not create backup")

    result = run_fix(dry_run=dry_run)

    if result.get("already_fixed"):
        print("\nNo action needed - already fixed.")
    elif result.get("error"):
        print(f"\nFailed: {result['error']}")
        sys.exit(1)
    elif dry_run:
        print("\nRun without --dry-run to apply.")
    else:
        print("\nFix complete.")


if __name__ == "__main__":
    main()
