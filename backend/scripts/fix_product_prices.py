"""
Repara Product.price usando el sale_price válido más reciente de inventory_history.
Solo actualiza productos con price=0 que tengan al menos un historical sale_price > 0.

Uso:
    python backend/scripts/fix_product_prices.py [--dry-run]
"""

import sys
from decimal import Decimal
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from app.db import SessionLocal, engine
from app.models import Base, InventoryHistory, Product


def find_latest_valid_prices(db):
    products = db.query(Product).filter(Product.active == True).all()
    updates = []

    for product in products:
        if product.price and product.price > Decimal("0"):
            continue

        latest = (
            db.query(InventoryHistory)
            .filter(
                InventoryHistory.product_id == product.id,
                InventoryHistory.sale_price > 0,
            )
            .order_by(InventoryHistory.period_date.desc())
            .first()
        )

        if latest and latest.sale_price and latest.sale_price > Decimal("0"):
            updates.append({
                "product_id": product.id,
                "product_name": product.name,
                "old_price": product.price,
                "new_price": latest.sale_price,
                "source_period": latest.period_date.isoformat()[:10],
            })

    return updates


def apply_updates(db, updates):
    for u in updates:
        product = db.get(Product, u["product_id"])
        if product:
            product.price = u["new_price"]
    db.commit()


def main():
    dry_run = "--dry-run" in sys.argv

    db = SessionLocal()
    try:
        updates = find_latest_valid_prices(db)

        print(f"Productos con price=0 y precio histórico disponible: {len(updates)}")
        for u in updates:
            print(f"  {u['product_name']:30s} price: {u['old_price']} -> {u['new_price']} (periodo: {u['source_period']})")

        if not dry_run and updates:
            apply_updates(db, updates)
            print(f"\n{len(updates)} precios actualizados.")
        elif dry_run:
            print("\nDRY RUN - no se modificó la DB.")
        else:
            print("\nNo hay precios que actualizar.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
