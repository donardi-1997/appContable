"""DIAN End-to-End Preflight Script."""
import os
import sys
import sqlite3

os.chdir(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.getcwd())

DB_PATH = os.path.join(os.getcwd(), 'gato_contable.db')

checks = []
errors = []
warnings = []


def check(name, condition, msg_ok="", msg_err=""):
    status = "PASS" if condition else "FAIL"
    checks.append((name, status, msg_ok if condition else msg_err))
    if not condition:
        errors.append(msg_err or name)


print("=" * 60)
print("PHASE 1: PREFLIGHT — DIAN END-TO-END VALIDATION")
print("=" * 60)

# ---- ENV CHECKS ----
print("\n--- CONFIGURATION (ENV) ---")

provider = os.environ.get("ELECTRONIC_INVOICE_PROVIDER", "")
check("ELECTRONIC_INVOICE_PROVIDER", provider != "",
      f"Provider: {provider}", "ELECTRONIC_INVOICE_PROVIDER not set")

environment = os.environ.get("DIAN_ENVIRONMENT", "")
check("DIAN_ENVIRONMENT", environment != "",
      f"Environment: {environment}", "DIAN_ENVIRONMENT not set")

if environment == "produccion":
    print("\n*** BLOCKED: PRODUCTION DETECTED. HALTING. ***")
    sys.exit(1)

software_id = os.environ.get("DIAN_SOFTWARE_ID", "")
check("DIAN_SOFTWARE_ID", software_id != "",
      f"Software ID: {software_id[:8]}..." if software_id else "",
      "DIAN_SOFTWARE_ID not set")

software_pin = os.environ.get("DIAN_SOFTWARE_PIN", "")
check("DIAN_SOFTWARE_PIN", software_pin != "",
      "Software PIN: configured", "DIAN_SOFTWARE_PIN not set")

software_provider_nit = os.environ.get("DIAN_SOFTWARE_PROVIDER_NIT", "")
check("DIAN_SOFTWARE_PROVIDER_NIT", software_provider_nit != "",
      "Software Provider NIT: configured", "DIAN_SOFTWARE_PROVIDER_NIT not set")

test_set_id = os.environ.get("DIAN_TEST_SET_ID", "")
if environment == "habilitacion":
    check("DIAN_TEST_SET_ID", test_set_id != "",
          "Test Set ID: configured", "DIAN_TEST_SET_ID required for habilitacion")
else:
    check("DIAN_TEST_SET_ID", True, "N/A (not habilitacion)")

technical_key = os.environ.get("DIAN_TECHNICAL_KEY", "")
check("DIAN_TECHNICAL_KEY", technical_key != "",
      "Technical key: configured", "DIAN_TECHNICAL_KEY not set (needed for CUFE)")

certificate_path = os.environ.get("DIAN_CERTIFICATE_PATH", "")
check("DIAN_CERTIFICATE_PATH", certificate_path != "",
      "Certificate path: configured", "DIAN_CERTIFICATE_PATH not set")

if certificate_path and os.path.exists(certificate_path):
    check("CERTIFICATE_FILE_EXISTS", True, "Certificate file exists")
    try:
        from cryptography.hazmat.primitives.serialization import pkcs12
        from datetime import datetime, timezone
        with open(certificate_path, "rb") as f:
            pfx_data = f.read()
        cert_pass = os.environ.get("DIAN_CERTIFICATE_PASSWORD", "")
        password_bytes = cert_pass.encode("utf-8") if cert_pass else None
        private_key, certificate, chain = pkcs12.load_key_and_certificates(pfx_data, password_bytes)
        check("CERTIFICATE_LOADABLE", True, "Certificate loadable: yes")
        check("PRIVATE_KEY_AVAILABLE", private_key is not None,
              "Private key: available", "Private key: NOT FOUND")
        check("CERTIFICATE_AVAILABLE", certificate is not None,
              "X509 certificate: available", "X509 certificate: NOT FOUND")
        if certificate:
            now = datetime.now(timezone.utc)
            if certificate.not_valid_after_utc < now:
                check("CERTIFICATE_EXPIRED", False, "",
                      f"Certificate EXPIRED on {certificate.not_valid_after_utc}")
            else:
                check("CERTIFICATE_NOT_EXPIRED", True,
                      f"Certificate valid until {certificate.not_valid_after_utc}")
    except FileNotFoundError:
        check("CERTIFICATE_FILE_EXISTS", False, "", f"Certificate file not found: {certificate_path}")
    except Exception as e:
        check("CERTIFICATE_LOADABLE", False, "", f"Certificate error: {str(e)[:100]}")
elif certificate_path:
    check("CERTIFICATE_FILE_EXISTS", False, "", f"Certificate file not found: {certificate_path}")

certificate_password = os.environ.get("DIAN_CERTIFICATE_PASSWORD", "")
check("DIAN_CERTIFICATE_PASSWORD", certificate_password != "",
      "Certificate password: configured", "DIAN_CERTIFICATE_PASSWORD not set")

nit = os.environ.get("DIAN_NIT", "")
check("DIAN_NIT", nit != "", "NIT: configured", "DIAN_NIT not set")

dv = os.environ.get("DIAN_DV", "")
check("DIAN_DV", dv != "", f"DV: {dv}", "DIAN_DV not set")

resolution_number = os.environ.get("DIAN_RESOLUTION_NUMBER", "")
check("DIAN_RESOLUTION_NUMBER", resolution_number != "",
      f"Resolution number: {resolution_number}", "DIAN_RESOLUTION_NUMBER not set")

resolution_prefix = os.environ.get("DIAN_RESOLUTION_PREFIX", "")
check("DIAN_RESOLUTION_PREFIX", resolution_prefix != "",
      f"Resolution prefix: {resolution_prefix}", "DIAN_RESOLUTION_PREFIX not set")

resolution_from = os.environ.get("DIAN_RESOLUTION_FROM", "")
check("DIAN_RESOLUTION_FROM", resolution_from != "",
      f"Resolution from: {resolution_from}", "DIAN_RESOLUTION_FROM not set")

resolution_to = os.environ.get("DIAN_RESOLUTION_TO", "")
check("DIAN_RESOLUTION_TO", resolution_to != "",
      f"Resolution to: {resolution_to}", "DIAN_RESOLUTION_TO not set")

resolution_start = os.environ.get("DIAN_RESOLUTION_START_DATE", "")
check("DIAN_RESOLUTION_START_DATE", resolution_start != "",
      f"Resolution start: {resolution_start}", "DIAN_RESOLUTION_START_DATE not set")

resolution_end = os.environ.get("DIAN_RESOLUTION_END_DATE", "")
check("DIAN_RESOLUTION_END_DATE", resolution_end != "",
      f"Resolution end: {resolution_end}", "DIAN_RESOLUTION_END_DATE not set")

# ---- DATABASE CHECKS ----
print("\n--- DATABASE ---")

if os.path.exists(DB_PATH):
    check("DATABASE_EXISTS", True, "Database found")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    check("TABLE_SALES", "sales" in tables, "Sales table exists", "Sales table not found")
    check("TABLE_ELECTRONIC_INVOICES", "electronic_invoices" in tables,
          "Electronic invoices table exists", "Electronic invoices table not found")
    check("TABLE_COMPANY_INFO", "company_info" in tables,
          "Company info table exists", "Company info table not found")

    if "sales" in tables:
        cur.execute("SELECT COUNT(*) FROM sales")
        count = cur.fetchone()[0]
        check("SALES_DATA", count > 0, f"Sales count: {count}", "No sales in database")

        cur.execute("SELECT id, sale_number, status, total FROM sales WHERE status='completada' ORDER BY id DESC LIMIT 5")
        completed = cur.fetchall()
        if completed:
            check("COMPLETED_SALES", True, f"Completed sales: {len(completed)}")
            print("  Completed sales:")
            for s in completed:
                print(f"    id={s[0]}, number={s[1]}, status={s[2]}, total={s[3]}")
        else:
            check("COMPLETED_SALES", False, "", "No completed sales found")

    if "company_info" in tables:
        cur.execute("SELECT id, company_name, nit, dv FROM company_info LIMIT 1")
        row = cur.fetchone()
        if row:
            check("COMPANY_INFO", True, f"Company info: configured")
            print(f"  Company: name={row[1]}, nit={row[2]}, dv={row[3]}")
        else:
            check("COMPANY_INFO", False, "", "No company info configured")

    if "electronic_invoices" in tables:
        cur.execute("SELECT COUNT(*) FROM electronic_invoices")
        ei_count = cur.fetchone()[0]
        print(f"  Electronic invoices in DB: {ei_count}")

    conn.close()
else:
    check("DATABASE_EXISTS", False, "", f"Database not found at {DB_PATH}")

# ---- .env FILE ----
print("\n--- ENV FILE ---")
env_path = os.path.join(os.getcwd(), '.env')
check("ENV_FILE", os.path.exists(env_path),
      ".env file exists", ".env file NOT found (only .env.example)")

# ---- REPORT ----
print("\n" + "=" * 60)
print("PREFLIGHT RESULT")
print("=" * 60)

any_critical_fail = any(c[1] == "FAIL" for c in checks)
ready = not any_critical_fail

print(f"\nREADY: {'YES' if ready else 'NO'}")
print(f"Environment: {environment or '(not set)'}")

if errors:
    print(f"\nErrors ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")

if warnings:
    print(f"\nWarnings ({len(warnings)}):")
    for w in warnings:
        print(f"  - {w}")

print(f"\nChecks passed: {sum(1 for c in checks if c[1] == 'PASS')}/{len(checks)}")

if not ready:
    print("\n*** NOT READY FOR DIAN SUBMISSION ***")
else:
    print("\n*** READY FOR DRY RUN ***")
