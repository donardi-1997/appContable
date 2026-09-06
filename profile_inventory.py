#!/usr/bin/env python3
"""Comprehensive profiling script for historical_inventory.json"""

import json
import re
import unicodedata
from collections import defaultdict, Counter
from datetime import datetime

FILE = r"C:\Users\25fel\Documents\appContableGato\backend\data\historical_inventory.json"

def load():
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def try_parse_date(key):
    key_clean = key.strip()
    months = {
        "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
        "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
        "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
        "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
        "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
        "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
    }
    upper = key_clean.upper().replace(" DE ", " ").replace(",", " ").replace("/", " ")
    # remove common noise
    upper = re.sub(r"\(.*?\)", "", upper).strip()

    # Try patterns
    # "28 MARZO 2026" or "28 MARZO"
    m = re.search(r"(\d{1,2})\s+([A-Z]+)\s*(\d{4})?", upper)
    if m:
        day = int(m.group(1))
        mon_str = m.group(2)
        year = int(m.group(3)) if m.group(3) else 2026
        month = months.get(mon_str)
        if month:
            try:
                return datetime(year, month, day)
            except ValueError:
                pass
    # "17 DE JUNIO" pattern already covered above
    # "01 AGOSTO"
    m = re.search(r"^(\d{1,2})\s+([A-Z]+)$", upper)
    if m:
        day = int(m.group(1))
        month = months.get(m.group(2))
        if month:
            try:
                return datetime(2026, month, day)
            except ValueError:
                pass
    # "14,15 AGOSTO" -> take first day
    m = re.search(r"(\d{1,2})\s*\d*\s+([A-Z]+)", upper)
    if m:
        day = int(m.group(1))
        month = months.get(m.group(2))
        if month:
            try:
                return datetime(2026, month, day)
            except ValueError:
                pass
    return None

def is_numeric(val):
    if val is None:
        return True  # missing is ok
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, str):
        val = val.strip()
        if val == "":
            return True
        try:
            float(val.replace(",", ""))
            return True
        except ValueError:
            return False
    return False

def to_number(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        val = val.strip()
        if val == "":
            return None
        try:
            return float(val.replace(",", ""))
        except ValueError:
            return None
    return None

def classify_row(row):
    if row is None:
        return "null"
    name = row.get("LA PATRONA VIP")
    if name is None:
        # Check if it's a DEUDORES/summary row
        c5 = row.get("Column5", "")
        if isinstance(c5, str) and "DEUDOR" in c5.upper():
            return "deudores_section"
        if isinstance(c5, str) and "DESCUADRE" in c5.upper():
            return "descuadre_summary"
        if isinstance(c5, str) and c5.strip().upper() in ("TOTAL",):
            return "summary"
        return "empty_name"
    if isinstance(name, str):
        name_up = name.strip().upper()
        if name_up == "TOTAL VENTAS":
            return "total_ventas"
        if name_up == "GASTOS":
            return "gastos_header"
        if name_up == "":
            c5 = row.get("Column5", "")
            if isinstance(c5, str) and "DEUDOR" in c5.upper():
                return "deudores_section"
            if isinstance(c5, str) and "DESCUADRE" in c5.upper():
                return "descuadre_summary"
            if isinstance(c5, str) and c5.strip().upper() == "TOTAL":
                return "summary"
            return "empty_name"
        if name_up in ("INVENTARIO",):
            return "title"
        if name_up in ("PRODUCTO",):
            return "header_row"
    if isinstance(name, (int, float)):
        return "gastos_data"
    # Has a non-empty string name and presumably product data
    return "product"

def main():
    data = load()
    sheet_keys = list(data.keys())

    print("=" * 80)
    print("1. ROOT STRUCTURE")
    print("=" * 80)
    print(f"Total sheets: {len(sheet_keys)}")
    for k in sheet_keys:
        rows = data[k]
        non_null = sum(1 for r in rows if r is not None)
        print(f"  {k!r}: {len(rows)} rows ({non_null} non-null)")

    print()
    print("=" * 80)
    print("2. ROW CLASSIFICATION PER SHEET")
    print("=" * 80)
    all_product_names = []
    price_map = defaultdict(lambda: defaultdict(set))  # product -> sheet -> set of prices
    null_analysis = defaultdict(lambda: defaultdict(int))  # col -> missing count
    negative_values = []
    zero_prices = []
    bool_in_numeric = []
    string_in_numeric = []
    encoding_issues = []
    extra_cols_data = defaultdict(list)  # col11/12/13 -> list of values
    gastos_data = {}
    deudores_data = {}
    descuadres_analysis = None

    for sheet_name, rows in data.items():
        counters = Counter()
        for r in rows:
            cls = classify_row(r)
            counters[cls] += 1
        print(f"\n--- {sheet_name!r} ---")
        for cls, cnt in sorted(counters.items()):
            print(f"  {cls}: {cnt}")

        # Process product rows, gastos, deudores, etc.
        in_gastos = False
        in_deudores = False
        gastos_expenses = []
        gastos_payments = []
        deudores_list = []

        for i, row in enumerate(rows):
            if row is None:
                continue
            cls = classify_row(row)

            if cls == "gastos_header":
                in_gastos = True
                in_deudores = False
                continue

            if cls == "total_ventas":
                in_gastos = False
                continue

            if cls == "deudores_section":
                in_deudores = True
                in_gastos = False
                continue

            if cls == "descuadre_summary":
                in_deudores = False
                continue

            if cls == "header_row" or cls == "title":
                continue

            if cls == "product":
                name = row.get("LA PATRONA VIP", "")
                if isinstance(name, str):
                    normalized = " ".join(name.strip().upper().split())
                    all_product_names.append(normalized)

                    # Price tracking
                    price = to_number(row.get("Column7"))
                    if price is not None:
                        price_map[normalized][sheet_name].add(price)

                    # Null/missing analysis for numeric cols
                    for col in ["Column3", "Column4", "Column5", "Column6", "Column7", "Column8", "Column9", "Column10"]:
                        val = row.get(col)
                        if val is None:
                            null_analysis[col]["null_count"] += 1
                        elif isinstance(val, str) and val.strip() == "":
                            null_analysis[col]["empty_string"] += 1
                        elif isinstance(val, bool):
                            bool_in_numeric.append((sheet_name, i, normalized, col, val))
                            null_analysis[col]["bool_count"] += 1
                        elif isinstance(val, str):
                            # Check if it's a numeric string
                            if not is_numeric(val):
                                string_in_numeric.append((sheet_name, i, normalized, col, val))
                                null_analysis[col]["string_count"] += 1

                    # Negative values
                    for col in ["Column3", "Column4", "Column5", "Column6", "Column7", "Column8", "Column9", "Column10"]:
                        n = to_number(row.get(col))
                        if n is not None and n < 0:
                            negative_values.append((sheet_name, i, normalized, col, row.get(col)))

                    # Zero prices
                    if price is not None and price == 0:
                        zero_prices.append((sheet_name, i, normalized))

                    # Encoding issues
                    if isinstance(name, str):
                        for ch in name:
                            if ord(ch) > 127:
                                cat = unicodedata.category(ch)
                                if cat.startswith('C') or ch == '\ufffd' or ch == '\x00':
                                    encoding_issues.append((sheet_name, i, repr(name)))
                                    break
                        # Also check for replacement char U+FFFD or common mojibake patterns
                        if '\ufffd' in name or '\x00' in name:
                            if (sheet_name, i, repr(name)) not in encoding_issues:
                                encoding_issues.append((sheet_name, i, repr(name)))

            # Gastos section
            if in_gastos and cls == "gastos_data":
                concept = row.get("Column3", "") if row else ""
                amount = row.get("LA PATRONA VIP") if row else None
                gastos_expenses.append((concept, amount))
                payment_method = row.get("Column5", "") if row else ""
                payment_amount = row.get("Column6") if row else None
                if payment_method:
                    gastos_payments.append((payment_method, payment_amount))

            # Gastos section - rows with empty name but gastos context
            if in_gastos and cls == "empty_name":
                concept = row.get("Column3", "") if row else ""
                amount = row.get("LA PATRONA VIP") if row else None
                payment_method = row.get("Column5", "") if row else ""
                payment_amount = row.get("Column6") if row else None
                if concept:
                    gastos_expenses.append((concept, amount))
                if payment_method:
                    gastos_payments.append((payment_method, payment_amount))

            # Deudores section
            if in_deudores and cls in ("empty_name", "product"):
                debtor_name = row.get("Column5", "")
                debtor_amount = row.get("Column6")
                if debtor_name and isinstance(debtor_name, str) and debtor_name.strip():
                    deudores_list.append((debtor_name.strip(), debtor_amount))

            # Extra columns
            for col in ["Column11", "Column12", "Column13"]:
                val = row.get(col)
                if val is not None:
                    extra_cols_data[col].append((sheet_name, i, val))

        if gastos_expenses or gastos_payments or deudores_list:
            gastos_data[sheet_name] = {"expenses": gastos_expenses, "payments": gastos_payments}
            deudores_data[sheet_name] = deudores_list

    print()
    print("=" * 80)
    print("3 & 4. UNIQUE PRODUCT NAMES")
    print("=" * 80)
    unique_products = sorted(set(all_product_names))
    print(f"Total unique normalized product names: {len(unique_products)}")
    print()
    for p in unique_products:
        print(f"  {p}")

    print()
    print("=" * 80)
    print("5. PRICE VARIANCE")
    print("=" * 80)
    flagged = 0
    for product in sorted(price_map.keys()):
        all_prices = set()
        for sheet, prices in price_map[product].items():
            all_prices.update(prices)
        if len(all_prices) > 1:
            flagged += 1
            print(f"  ** {product}: {sorted(all_prices)}")
    print(f"\nProducts with >1 price: {flagged}")
    # Also show all products with their prices
    print("\nAll product prices:")
    for product in sorted(price_map.keys()):
        all_prices = set()
        for sheet, prices in price_map[product].items():
            all_prices.update(prices)
        print(f"  {product}: {sorted(all_prices)}")

    print()
    print("=" * 80)
    print("6. DATE PARSING")
    print("=" * 80)
    for k in sheet_keys:
        parsed = try_parse_date(k)
        print(f"  {k!r:40s} -> {parsed}")

    print()
    print("=" * 80)
    print("7. COLUMN PRESENCE PER SHEET")
    print("=" * 80)
    target_cols = ["Column3", "Column4", "Column5", "Column6", "Column7", "Column8", "Column9", "Column10"]
    for sheet_name, rows in data.items():
        present = set()
        for r in rows:
            if r is not None:
                for c in target_cols:
                    if c in r:
                        present.add(c)
        missing = [c for c in target_cols if c not in present]
        print(f"  {sheet_name!r}: present={sorted(present)}, missing={missing}")

    print()
    print("=" * 80)
    print("8. NULL/MISSING ANALYSIS (product rows)")
    print("=" * 80)
    for col in target_cols:
        stats = null_analysis.get(col, {})
        total_product_rows = len(all_product_names)
        null_c = stats.get("null_count", 0)
        empty_s = stats.get("empty_string", 0)
        bool_c = stats.get("bool_count", 0)
        str_c = stats.get("string_count", 0)
        present = total_product_rows - null_c - empty_s
        print(f"  {col}: present={present}, null={null_c}, empty_string={empty_s}, bool={bool_c}, non_numeric_string={str_c}")

    print()
    print("=" * 80)
    print("9. NEGATIVE VALUES")
    print("=" * 80)
    if negative_values:
        for sheet, idx, name, col, val in negative_values:
            print(f"  Sheet={sheet!r}, row={idx}, product={name!r}, {col}={val}")
    else:
        print("  None found.")
    print(f"  Total: {len(negative_values)}")

    print()
    print("=" * 80)
    print("10. ZERO PRICES")
    print("=" * 80)
    if zero_prices:
        for sheet, idx, name in zero_prices:
            print(f"  Sheet={sheet!r}, row={idx}, product={name!r}")
    else:
        print("  None found.")
    print(f"  Total: {len(zero_prices)}")

    print()
    print("=" * 80)
    print("11. DESCUADRES SHEET ANALYSIS")
    print("=" * 80)
    if "DESCUADRES" in data:
        rows = data["DESCUADRES"]
        print(f"Total rows: {len(rows)}")
        for i, r in enumerate(rows):
            if r is not None:
                print(f"  Row {i}: {json.dumps(r, ensure_ascii=False)[:300]}")
            else:
                print(f"  Row {i}: null")
    else:
        print("  DESCUADRES sheet not found.")

    print()
    print("=" * 80)
    print("12. GASTOS SECTION ANALYSIS")
    print("=" * 80)
    for sheet_name in sheet_keys:
        if sheet_name in gastos_data:
            gd = gastos_data[sheet_name]
            print(f"\n--- {sheet_name!r} ---")
            if gd["expenses"]:
                print("  Expenses (concept -> amount):")
                for concept, amount in gd["expenses"]:
                    print(f"    {concept!r}: {amount}")
            if gd["payments"]:
                print("  Payment methods:")
                for method, amount in gd["payments"]:
                    print(f"    {method!r}: {amount}")

    print()
    print("=" * 80)
    print("13. DEUDORES SECTION")
    print("=" * 80)
    for sheet_name in sheet_keys:
        if sheet_name in deudores_data and deudores_data[sheet_name]:
            print(f"\n--- {sheet_name!r} ---")
            for name, amount in deudores_data[sheet_name]:
                print(f"  {name!r}: {amount}")

    print()
    print("=" * 80)
    print("14. EXTRA COLUMNS (Column11, Column12, Column13)")
    print("=" * 80)
    for col in ["Column11", "Column12", "Column13"]:
        entries = extra_cols_data.get(col, [])
        print(f"\n--- {col}: {len(entries)} occurrences ---")
        type_counts = Counter()
        sample_values = []
        for sheet, idx, val in entries:
            type_counts[type(val).__name__] += 1
            if len(sample_values) < 15:
                sample_values.append((sheet, idx, val))
        print(f"  Type distribution: {dict(type_counts)}")
        print(f"  Sample values:")
        for sheet, idx, val in sample_values:
            print(f"    Sheet={sheet!r}, row={idx}: {val!r}")

    print()
    print("=" * 80)
    print("15. BOOLEAN VALUES IN NUMERIC FIELDS")
    print("=" * 80)
    if bool_in_numeric:
        for sheet, idx, name, col, val in bool_in_numeric:
            print(f"  Sheet={sheet!r}, row={idx}, product={name!r}, {col}={val}")
    else:
        print("  None found.")
    print(f"  Total: {len(bool_in_numeric)}")

    print()
    print("=" * 80)
    print("16. STRING VALUES IN NUMERIC FIELDS (non-numeric strings)")
    print("=" * 80)
    if string_in_numeric:
        for sheet, idx, name, col, val in string_in_numeric:
            print(f"  Sheet={sheet!r}, row={idx}, product={name!r}, {col}={val!r}")
    else:
        print("  None found.")
    print(f"  Total: {len(string_in_numeric)}")

    print()
    print("=" * 80)
    print("17. ENCODING ISSUES IN PRODUCT NAMES")
    print("=" * 80)
    if encoding_issues:
        seen = set()
        for sheet, idx, name_repr in encoding_issues:
            key = (sheet, idx, name_repr)
            if key not in seen:
                seen.add(key)
                print(f"  Sheet={sheet!r}, row={idx}: {name_repr}")
    else:
        print("  None found with replacement chars. Checking for other mojibake patterns...")
    # Broader check: any non-ASCII in product names
    print("\n  All non-ASCII characters in product names:")
    non_ascii_products = set()
    for sheet_name, rows in data.items():
        for i, r in enumerate(rows):
            if r is None:
                continue
            name = r.get("LA PATRONA VIP")
            if isinstance(name, str):
                non_ascii = [ch for ch in name if ord(ch) > 127]
                if non_ascii:
                    for ch in non_ascii:
                        try:
                            char_name = unicodedata.name(ch)
                        except ValueError:
                            char_name = "UNKNOWN"
                        non_ascii_products.add((name.strip(), ch, char_name, f"U+{ord(ch):04X}"))
    if non_ascii_products:
        for name, ch, char_name, codepoint in sorted(non_ascii_products):
            print(f"    {name!r}: contains {ch!r} ({char_name}, {codepoint})")
    else:
        print("    None found.")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Sheets: {len(sheet_keys)}")
    print(f"Unique products: {len(unique_products)}")
    print(f"Products with price variance: {flagged}")
    print(f"Negative values: {len(negative_values)}")
    print(f"Zero prices: {len(zero_prices)}")
    print(f"Booleans in numeric fields: {len(bool_in_numeric)}")
    print(f"Strings in numeric fields: {len(string_in_numeric)}")
    print(f"Encoding issues (replacement char): {len(encoding_issues)}")
    print(f"Non-ASCII product names: {len(non_ascii_products)}")

if __name__ == "__main__":
    main()
