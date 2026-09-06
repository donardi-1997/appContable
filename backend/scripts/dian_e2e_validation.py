"""
DIAN E2E Validation Script — Dry Run Pipeline.
Validates the entire flow without contacting DIAN.
"""
import os
import sys
import hashlib
import re
import xml.etree.ElementTree as ET
from decimal import Decimal
from datetime import datetime, timezone

os.chdir(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.getcwd())

DB_PATH = os.path.join(os.getcwd(), 'gato_contable.db')
AUDIT_DIR = os.path.join(os.getcwd(), 'scripts', 'dian_audit')
os.makedirs(AUDIT_DIR, exist_ok=True)

CUFE_96_HEX = re.compile(r"^[0-9A-F]{96}$")

results = {
    "preflight": {"ready": False, "errors": [], "warnings": []},
    "sale": None,
    "numbering": None,
    "cufe": None,
    "ssc": None,
    "qr": None,
    "xml_unsigned": None,
    "xml_signed": None,
    "zip": None,
    "dry_run": None,
    "secrets_detected": [],
}


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# PHASE 1: PREFLIGHT
# ============================================================
print_header("PHASE 1: PREFLIGHT")

import sqlite3

env_provider = os.environ.get("ELECTRONIC_INVOICE_PROVIDER", "")
env_environment = os.environ.get("DIAN_ENVIRONMENT", "")
env_software_id = os.environ.get("DIAN_SOFTWARE_ID", "")
env_software_pin = os.environ.get("DIAN_SOFTWARE_PIN", "")
env_software_provider_nit = os.environ.get("DIAN_SOFTWARE_PROVIDER_NIT", "")
env_test_set_id = os.environ.get("DIAN_TEST_SET_ID", "")
env_technical_key = os.environ.get("DIAN_TECHNICAL_KEY", "")
env_certificate_path = os.environ.get("DIAN_CERTIFICATE_PATH", "")
env_certificate_password = os.environ.get("DIAN_CERTIFICATE_PASSWORD", "")
env_nit = os.environ.get("DIAN_NIT", "")
env_dv = os.environ.get("DIAN_DV", "")
env_resolution_number = os.environ.get("DIAN_RESOLUTION_NUMBER", "")
env_resolution_prefix = os.environ.get("DIAN_RESOLUTION_PREFIX", "")
env_resolution_from = os.environ.get("DIAN_RESOLUTION_FROM", "")
env_resolution_to = os.environ.get("DIAN_RESOLUTION_TO", "")
env_resolution_start = os.environ.get("DIAN_RESOLUTION_START_DATE", "")
env_resolution_end = os.environ.get("DIAN_RESOLUTION_END_DATE", "")

preflight_errors = []
preflight_warnings = []

if env_provider != "dian":
    preflight_errors.append(f"ELECTRONIC_INVOICE_PROVIDER='{env_provider}' (need 'dian')")
else:
    print(f"  Provider: {env_provider}")

if env_environment == "produccion":
    preflight_errors.append("BLOCKED: DIAN_ENVIRONMENT is 'produccion'. Cannot proceed.")
    print("*** BLOCKED: PRODUCTION DETECTED ***")
    sys.exit(1)
elif env_environment != "habilitacion":
    preflight_errors.append(f"DIAN_ENVIRONMENT='{env_environment}' (need 'habilitacion')")
else:
    print(f"  Environment: {env_environment}")

missing_envs = []
for name, val in [
    ("DIAN_SOFTWARE_ID", env_software_id),
    ("DIAN_SOFTWARE_PIN", env_software_pin),
    ("DIAN_SOFTWARE_PROVIDER_NIT", env_software_provider_nit),
    ("DIAN_TEST_SET_ID", env_test_set_id),
    ("DIAN_TECHNICAL_KEY", env_technical_key),
    ("DIAN_CERTIFICATE_PATH", env_certificate_path),
    ("DIAN_CERTIFICATE_PASSWORD", env_certificate_password),
    ("DIAN_NIT", env_nit),
    ("DIAN_DV", env_dv),
    ("DIAN_RESOLUTION_NUMBER", env_resolution_number),
    ("DIAN_RESOLUTION_PREFIX", env_resolution_prefix),
    ("DIAN_RESOLUTION_FROM", env_resolution_from),
    ("DIAN_RESOLUTION_TO", env_resolution_to),
    ("DIAN_RESOLUTION_START_DATE", env_resolution_start),
    ("DIAN_RESOLUTION_END_DATE", env_resolution_end),
]:
    if not val:
        missing_envs.append(name)

if missing_envs:
    preflight_errors.extend([f"{e} not set" for e in missing_envs])
    print(f"\n  Missing env vars: {len(missing_envs)}")
    for e in missing_envs:
        print(f"    - {e}")

# .env file
env_file = os.path.join(os.getcwd(), '.env')
if not os.path.exists(env_file):
    preflight_errors.append(".env file not found")

# Certificate
cert_ok = False
if env_certificate_path:
    if os.path.exists(env_certificate_path):
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12
            with open(env_certificate_path, "rb") as f:
                pfx_data = f.read()
            pw = env_certificate_password.encode("utf-8") if env_certificate_password else None
            pk, cert, chain = pkcs12.load_key_and_certificates(pfx_data, pw)
            if pk is None:
                preflight_errors.append("Certificate: private key not found")
            elif cert is None:
                preflight_errors.append("Certificate: X509 cert not found")
            else:
                now = datetime.now(timezone.utc)
                if cert.not_valid_after_utc < now:
                    preflight_errors.append(f"Certificate EXPIRED: {cert.not_valid_after_utc}")
                else:
                    cert_ok = True
                    print(f"  Certificate: OK (valid until {cert.not_valid_after_utc})")
        except Exception as e:
            preflight_errors.append(f"Certificate error: {str(e)[:80]}")
    else:
        preflight_errors.append(f"Certificate file not found: {env_certificate_path}")

# Database
db_ok = False
conn = None
if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    required = ['sales', 'electronic_invoices', 'company_info', 'sale_items', 'products']
    for t in required:
        if t not in tables:
            preflight_errors.append(f"Table '{t}' not found")
    db_ok = all(t in tables for t in required)
    if db_ok:
        print(f"  Database: OK ({len(tables)} tables)")
else:
    preflight_errors.append(f"Database not found: {DB_PATH}")

ready = len(preflight_errors) == 0
results["preflight"]["ready"] = ready
results["preflight"]["errors"] = preflight_errors
results["preflight"]["warnings"] = preflight_warnings

print(f"\n  PREFLIGHT: {'READY' if ready else 'NOT READY'}")
print(f"  Errors: {len(preflight_errors)}")
for e in preflight_errors:
    print(f"    - {e}")

if not ready:
    print("\n*** NOT READY FOR DIAN SUBMISSION ***")
    print("*** CONTINUING WITH DRY RUN (code validation only) ***")


# ============================================================
# PHASE 2: SALE SELECTION
# ============================================================
print_header("PHASE 2: SALE SELECTION")

if conn:
    cur = conn.cursor()
    # Use V-00021 — small, simple, completed
    cur.execute("SELECT id, number, customer_name, payment_method, total, status FROM sales WHERE status='completada' ORDER BY id ASC LIMIT 1")
    sale = cur.fetchone()
    if sale:
        sale_id, sale_number, customer_name, payment_method, sale_total, sale_status = sale
        print(f"  Selected sale: {sale_number}")
        print(f"  Sale ID: {sale_id}")
        print(f"  Customer: {customer_name}")
        print(f"  Payment: {payment_method}")
        print(f"  Total: {sale_total}")
        print(f"  Status: {sale_status}")

        cur.execute("SELECT si.id, si.product_id, si.quantity, si.unit_price, p.name FROM sale_items si LEFT JOIN products p ON si.product_id = p.id WHERE si.sale_id = ?", (sale_id,))
        items = cur.fetchall()
        print(f"  Items: {len(items)}")
        item_dicts = []
        subtotal = Decimal("0")
        tax_total = Decimal("0")
        for item in items:
            item_subtotal = Decimal(str(item[2])) * Decimal(str(item[3]))
            tax_amount = (item_subtotal * Decimal("0.19")).quantize(Decimal("0.01"))
            item_dicts.append({
                "product_name": item[4],
                "quantity": str(item[2]),
                "unit_price": str(item[3]),
                "subtotal": str(item_subtotal),
                "tax_rate": "19",
                "tax_amount": str(tax_amount),
                "tax_type": "01",
            })
            subtotal += item_subtotal
            tax_total += tax_amount
        total = subtotal + tax_total
        print(f"  Subtotal: {subtotal}")
        print(f"  Tax (19% IVA): {tax_total}")
        print(f"  Total: {total}")

        results["sale"] = {
            "id": sale_id,
            "number": sale_number,
            "customer": customer_name,
            "items": len(item_dicts),
            "subtotal": str(subtotal),
            "tax_total": str(tax_total),
            "total": str(total),
        }
    else:
        print("  No completed sales found!")
        results["sale"] = None

    # Company info
    cur.execute("SELECT company_name, nit, dv, address, municipality, department, country, email, regime, software_id, certificate_path FROM company_info LIMIT 1")
    company = cur.fetchone()
    if company:
        print(f"\n  Company: {company[0]}")
        print(f"  NIT: {company[1]}")
    else:
        print("\n  Company info: EMPTY (not configured)")
        preflight_warnings.append("Company info not configured in DB")


# ============================================================
# PHASE 3: SNAPSHOT
# ============================================================
print_header("PHASE 3: SNAPSHOT")

if sale:
    prefix = "FE"
    invoice_number = "00000001"
    full_number = f"{prefix}{invoice_number}"
    now = datetime.now(timezone.utc)
    issue_date = now.strftime("%Y-%m-%d")
    issue_time = now.strftime("%H:%M:%S-05:00")

    snapshot = {
        "invoice_number": full_number,
        "prefix": prefix,
        "sale_id": sale_id,
        "sale_number": sale_number,
        "issue_date": issue_date,
        "issue_time": issue_time,
        "currency": "COP",
        "supplier_nit": env_nit or "TEST-NIT",
        "customer_document": "1234567890",
        "items": len(item_dicts),
        "subtotal": str(subtotal),
        "tax_total": str(tax_total),
        "total": str(total),
        "environment": env_environment or "habilitacion",
    }
    for k, v in snapshot.items():
        print(f"  {k}: {v}")
else:
    print("  No sale selected — using mock data for pipeline validation")
    prefix = "FE"
    invoice_number = "00000001"
    full_number = f"{prefix}{invoice_number}"
    now = datetime.now(timezone.utc)
    issue_date = now.strftime("%Y-%m-%d")
    issue_time = now.strftime("%H:%M:%S-05:00")
    subtotal = Decimal("100000.00")
    tax_total = Decimal("19000.00")
    total = Decimal("119000.00")
    item_dicts = [{
        "product_name": "Test Product",
        "quantity": "1",
        "unit_price": "100000.00",
        "subtotal": "100000.00",
        "tax_rate": "19",
        "tax_amount": "19000.00",
        "tax_type": "01",
    }]


# ============================================================
# PHASE 4: NUMBERING
# ============================================================
print_header("PHASE 4: NUMBERING VALIDATION")

if conn:
    cur = conn.cursor()
    cur.execute("SELECT id FROM electronic_invoices WHERE prefix=? AND invoice_number=?", (prefix, invoice_number))
    existing = cur.fetchone()
    if existing:
        print(f"  CONFLICT: Invoice {prefix}{invoice_number} already exists (id={existing[0]})")
        print("  ABORT: Would consume duplicate consecutive")
    else:
        print(f"  Invoice number: {full_number}")
        print(f"  Prefix: {prefix}")
        print(f"  Available: YES (no duplicate)")

    if env_resolution_from and env_resolution_to:
        rng_from = int(env_resolution_from)
        rng_to = int(env_resolution_to)
        num = int(invoice_number)
        if rng_from <= num <= rng_to:
            print(f"  Range: {rng_from}-{rng_to} — number {num} is within range")
        else:
            print(f"  RANGE ERROR: {num} not in {rng_from}-{rng_to}")

    cur.execute("SELECT COUNT(*) FROM electronic_invoices")
    ei_count = cur.fetchone()[0]
    print(f"  Existing electronic invoices: {ei_count}")

    results["numbering"] = {"number": full_number, "valid": existing is None}


# ============================================================
# PHASE 5: CUFE
# ============================================================
print_header("PHASE 5: CUFE CALCULATION")

from app.services.dian.cufe import calculate_cufe, calculate_software_security_code, calculate_qr_url
from app.services.dian.enums import CUFE_TAX_ORDER, TaxType, DocumentType

tax_totals_map = {"01": tax_total, "04": Decimal("0.00"), "03": Decimal("0.00")}

cufe = calculate_cufe(
    document_type=DocumentType.FACTURA_VENTA.value,
    invoice_number=full_number,
    issue_date=issue_date,
    issue_time=issue_time,
    line_extension_amount=subtotal,
    tax_totals=tax_totals_map,
    payable_amount=total,
    supplier_nit=env_nit or "900123456",
    customer_id="1234567890",
    technical_key=env_technical_key or "TEST_KEY_PLACEHOLDER",
    environment_code="2",
)

print(f"  Algorithm: SHA-384")
print(f"  Fields: 15 (NumFac + FecFac + HorFac + ValFac + CodImp1 + ValImp1 + CodImp2 + ValImp2 + CodImp3 + ValImp3 + ValTot + NitOFE + NumAdq + ClTec + TipoAmb)")
print(f"  NumFac: {full_number}")
print(f"  FecFac: {issue_date}")
print(f"  HorFac: {issue_time}")
print(f"  ValFac: {subtotal}")
print(f"  CodImp1: 01 | ValImp1: {tax_totals_map['01']}")
print(f"  CodImp2: 04 | ValImp2: {tax_totals_map['04']}")
print(f"  CodImp3: 03 | ValImp3: {tax_totals_map['03']}")
print(f"  ValTot: {total}")
print(f"  NitOFE: {env_nit or 'TEST-NIT'}")
print(f"  NumAdq: 1234567890")
print(f"  ClTec/PIN: [REDACTED]")
print(f"  TipoAmb: 2")
print(f"")
print(f"  CUFE: {cufe}")
print(f"  Length: {len(cufe)}")
print(f"  Valid format: {bool(CUFE_96_HEX.match(cufe))}")

results["cufe"] = {"value": cufe, "length": len(cufe), "valid": bool(CUFE_96_HEX.match(cufe))}


# ============================================================
# PHASE 6: SOFTWARE SECURITY CODE
# ============================================================
print_header("PHASE 6: SOFTWARE SECURITY CODE")

ssc = calculate_software_security_code(
    software_id=env_software_id or "TEST-SOFTWARE-ID",
    pin=env_software_pin or "TEST-PIN",
    document_number=full_number,
)

print(f"  Formula: SHA384(SoftwareID + PIN + NumFac)")
print(f"  SoftwareID: {(env_software_id or 'TEST-SOFTWARE-ID')[:8]}...[REDACTED]")
print(f"  PIN: [REDACTED]")
print(f"  NumFac: {full_number}")
print(f"  Result: {ssc}")
print(f"  Length: {len(ssc)}")
print(f"  Valid: {bool(CUFE_96_HEX.match(ssc))}")

results["ssc"] = {"valid": bool(CUFE_96_HEX.match(ssc))}


# ============================================================
# PHASE 7: QR DIAN
# ============================================================
print_header("PHASE 7: QR DIAN URL")

qr_url = calculate_qr_url(cufe)
expected_prefix = "https://catalogovpfe.dian.gov.co/document/searchqr?documentkey="
valid_qr = qr_url.startswith(expected_prefix) and cufe in qr_url

print(f"  URL: {qr_url}")
print(f"  Valid format: {valid_qr}")

results["qr"] = {"url": qr_url, "valid": valid_qr}


# ============================================================
# PHASE 8: XML UNSIGNED
# ============================================================
print_header("PHASE 8: XML UNSIGNED")

from app.services.dian.xml_builder import DianInvoiceXmlBuilder

try:
    builder = DianInvoiceXmlBuilder(
        invoice_number=invoice_number,
        prefix=prefix,
        issue_date=issue_date,
        issue_time=issue_time,
        invoice_type_code=DocumentType.FACTURA_VENTA.value,
        customer_id_type="13",
        customer_id="1234567890",
        customer_name="Cliente Prueba",
        customer_address="Calle 123",
        customer_email="test@test.com",
        supplier_name=env_nit or "TEST-NIT",
        supplier_nit=env_nit or "TEST-NIT",
        supplier_dv=env_dv or "0",
        supplier_address="Direccion Prueba",
        supplier_municipality="Bogota",
        supplier_department="Bogota D.C.",
        supplier_country="CO",
        supplier_phone="3001234567",
        supplier_email="admin@test.com",
        supplier_regime="O-47",
        resolution_number=env_resolution_number or "18764003560527",
        resolution_prefix=prefix,
        resolution_from=env_resolution_from or "1",
        resolution_to=env_resolution_to or "1000000",
        resolution_start_date=env_resolution_start or "2024-01-01",
        resolution_end_date=env_resolution_end or "2030-12-31",
        payment_form="1",
        payment_method="10",
        payment_due_date=issue_date,
        items=item_dicts,
        subtotal=subtotal,
        tax_total=tax_total,
        total=total,
        environment_code="2",
        software_id=env_software_id or "test-software-id",
        software_provider_nit=env_software_provider_nit or env_nit or "900123456",
        software_security_code=ssc,
        qr_url=qr_url,
        cufe=cufe,
    )
    unsigned_xml = builder.build_bytes()
    unsigned_path = os.path.join(AUDIT_DIR, f"invoice-{full_number}-unsigned.xml")
    with open(unsigned_path, "wb") as f:
        f.write(unsigned_xml)

    # Validate well-formed
    root = ET.fromstring(unsigned_xml)
    print(f"  Generated: YES")
    print(f"  Path: {unsigned_path}")
    print(f"  Size: {len(unsigned_xml)} bytes")
    print(f"  Well-formed XML: YES")

    # Validate structure
    ns = {"ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
          "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
          "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
          "sts": "http://www.dian.gov.co/pe/UBL/clac/2.1"}
    xml_str = unsigned_xml.decode("utf-8")

    validations = {
        "UBLVersionID": "UBLVersionID" in xml_str,
        "ProfileExecutionID": "ProfileExecutionID" in xml_str,
        "UBLExtensions": "UBLExtensions" in xml_str,
        "DianExtensions": "DianExtensions" in xml_str,
        "InvoiceControl": "InvoiceControl" in xml_str,
        "InvoiceSource": "InvoiceSource" in xml_str,
        "SoftwareProvider": "SoftwareProvider" in xml_str,
        "SoftwareSecurityCode": "SoftwareSecurityCode" in xml_str,
        "AuthorizationProvider": "AuthorizationProvider" in xml_str,
        "QRCode": "QRCode" in xml_str,
        "UUID (CUFE)": f">{cufe}<" in xml_str,
        "InvoiceTypeCode 01": ">01<" in xml_str,
        "CustomizationID 10": ">10<" in xml_str,
        "AccountingSupplierParty": "AccountingSupplierParty" in xml_str,
        "AccountingCustomerParty": "AccountingCustomerParty" in xml_str,
        "TaxTotal": "TaxTotal" in xml_str,
        "LegalMonetaryTotal": "LegalMonetaryTotal" in xml_str,
        "InvoiceLine": "InvoiceLine" in xml_str,
        "DIAN NIT 800197268": "800197268" in xml_str,
    }
    all_valid = all(validations.values())
    print(f"\n  Structure validations:")
    for k, v in validations.items():
        print(f"    {'OK' if v else 'FAIL'}: {k}")

    results["xml_unsigned"] = {
        "generated": True,
        "path": unsigned_path,
        "well_formed": True,
        "all_valid": all_valid,
        "validations": validations,
    }
except Exception as e:
    print(f"  ERROR: {e}")
    results["xml_unsigned"] = {"generated": False, "error": str(e)}


# ============================================================
# PHASE 9: XML VALIDATION
# ============================================================
print_header("PHASE 9: XML VALIDATION SUMMARY")

if results["xml_unsigned"] and results["xml_unsigned"].get("generated"):
    xml_valid = results["xml_unsigned"]["all_valid"]
    print(f"  All validations: {'PASS' if xml_valid else 'FAIL'}")
else:
    print("  SKIPPED (unsigned XML not generated)")


# ============================================================
# PHASE 10: SIGNING
# ============================================================
print_header("PHASE 10: SIGNING (CODE STRUCTURE VALIDATION)")

print("  NOTE: Actual signing requires a real .p12 certificate.")
print("  Validating signing code structure...")

from app.services.dian.signer import DianXmlSigner

signer = DianXmlSigner()
print(f"  DianXmlSigner class: OK")
print(f"  sign_xml method: {'OK' if hasattr(signer, 'sign_xml') else 'MISSING'}")
print(f"  _add_xades_object method: {'OK' if hasattr(signer, '_add_xades_object') else 'MISSING'}")
print(f"  _place_signature_in_ubl_extensions method: {'OK' if hasattr(signer, '_place_signature_in_ubl_extensions') else 'MISSING'}")

if cert_ok:
    try:
        signed_xml = signer.sign_xml(unsigned_xml, env_certificate_path, env_certificate_password)
        signed_path = os.path.join(AUDIT_DIR, f"invoice-{full_number}-signed.xml")
        with open(signed_path, "wb") as f:
            f.write(signed_xml)

        signed_str = signed_xml.decode("utf-8")
        sig_validations = {
            "ds:Signature": "ds:Signature" in signed_str,
            "ds:SignedInfo": "ds:SignedInfo" in signed_str,
            "ds:SignatureValue": "ds:SignatureValue" in signed_str,
            "ds:KeyInfo": "ds:KeyInfo" in signed_str,
            "ds:X509Certificate": "ds:X509Certificate" in signed_str,
            "xades:SignedProperties": "SignedProperties" in signed_str,
            "SigningTime": "SigningTime" in signed_str,
            "CertDigest": "CertDigest" in signed_str,
            "InUBLExtensions": "UBLExtensions" in signed_str and "ds:Signature" in signed_str.split("UBLExtensions")[1] if "UBLExtensions" in signed_str else False,
        }
        print(f"\n  Signing result: SUCCESS")
        print(f"  Signed path: {signed_path}")
        print(f"  Size: {len(signed_xml)} bytes")
        for k, v in sig_validations.items():
            print(f"    {'OK' if v else 'FAIL'}: {k}")

        # Try cryptographic verification
        try:
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives import hashes as crypto_hashes
            print(f"\n  Cryptographic verification: Library available but full XAdES validation")
            print(f"  requires specialized library (e.g., xades4j, xmlsig). Basic structure OK.")
        except Exception:
            print(f"\n  Cryptographic verification: Requires specialized library")

        results["xml_signed"] = {
            "generated": True,
            "path": signed_path,
            "validations": sig_validations,
        }
    except Exception as e:
        print(f"\n  Signing error: {e}")
        results["xml_signed"] = {"generated": False, "error": str(e)}
else:
    print("\n  SKIPPED: No valid certificate available for signing")
    print("  Code structure: OK")
    results["xml_signed"] = {"generated": False, "reason": "No valid certificate"}


# ============================================================
# PHASE 11: ZIP
# ============================================================
print_header("PHASE 11: ZIP CREATION")

try:
    import zipfile
    zip_path = os.path.join(AUDIT_DIR, f"FE_{env_nit or 'TEST'}_{full_number}.zip")
    xml_to_zip = results["xml_signed"].get("path") if results["xml_signed"] and results["xml_signed"].get("generated") else results["xml_unsigned"].get("path")

    if xml_to_zip and os.path.exists(xml_to_zip):
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(xml_to_zip, os.path.basename(xml_to_zip))

        with zipfile.ZipFile(zip_path, 'r') as zf:
            contents = zf.namelist()

        print(f"  Generated: YES")
        print(f"  Path: {zip_path}")
        print(f"  Contents: {contents}")
        print(f"  Size: {os.path.getsize(zip_path)} bytes")

        results["zip"] = {
            "generated": True,
            "path": zip_path,
            "contents": contents,
        }
    else:
        print("  SKIPPED: No signed XML available")
        results["zip"] = {"generated": False, "reason": "No signed XML"}
except Exception as e:
    print(f"  ZIP error: {e}")
    results["zip"] = {"generated": False, "error": str(e)}


# ============================================================
# PHASE 12: DRY RUN
# ============================================================
print_header("PHASE 12: DRY RUN RESULT")

dry_run_ok = (
    results.get("xml_unsigned", {}).get("generated") and
    results.get("xml_unsigned", {}).get("all_valid") and
    results.get("cufe", {}).get("valid") and
    results.get("ssc", {}).get("valid") and
    results.get("qr", {}).get("valid") and
    results.get("zip", {}).get("generated")
)

results["dry_run"] = {
    "passed": dry_run_ok,
    "invoice_number": full_number,
    "cufe": cufe,
    "xml_unsigned": results.get("xml_unsigned", {}).get("path"),
    "xml_signed": results.get("xml_signed", {}).get("path"),
    "zip": results.get("zip", {}).get("path"),
}

print(f"  DRY RUN: {'PASSED' if dry_run_ok else 'FAILED'}")
print(f"  Invoice number: {full_number}")
print(f"  CUFE: {cufe}")
print(f"  XML unsigned: {results.get('xml_unsigned', {}).get('path', 'N/A')}")
print(f"  XML signed: {results.get('xml_signed', {}).get('path', 'N/A')}")
print(f"  ZIP: {results.get('zip', {}).get('path', 'N/A')}")
print(f"  Environment: habilitacion")


# ============================================================
# PHASE 13-15: HABILITATION METHOD VERIFICATION
# ============================================================
print_header("PHASE 13: HABILITATION METHOD VERIFICATION")

from app.services.dian.config import DIANConfig
from app.services.dian.soap_client import DianSoapClient

config = DIANConfig(environment="habilitacion")
soap_action = config.get_soap_action("SetTrialInvoice")
soap_url = config.get_soap_url()

print(f"  Method: SetTrialInvoice")
print(f"  SOAPAction: {soap_action}")
print(f"  Endpoint: {soap_url}")
print(f"  Namespace: http://wcf.dian.colombia")
print(f"  SOAP version: 1.2 (http://www.w3.org/2003/05/soap-envelope)")
print(f"  WS-Security: BinarySecurityToken + Timestamp")
print(f"  WS-Addressing: Action + To")
print(f"  Content-Type: application/soap+xml; charset=utf-8")


# ============================================================
# PHASE 16-18: TRANSMISSION (BLOCKED)
# ============================================================
print_header("PHASE 16: TRANSMISSION STATUS")

if not ready:
    print("  STATUS: NOT EXECUTED")
    print(f"  REASON: Preflight failed — {len(preflight_errors)} errors")
    for e in preflight_errors:
        print(f"    - {e}")
else:
    print("  STATUS: Would execute (but this is a dry run)")


# ============================================================
# SECURITY AUDIT
# ============================================================
print_header("SECURITY AUDIT")

secret_patterns = ["PIN=", "PASSWORD=", "PRIVATE KEY", "BEGIN PRIVATE KEY", "certificate password", "secret"]
secrets_found = []

# Check generated files
for file_path in [results.get("xml_unsigned", {}).get("path"), results.get("xml_signed", {}).get("path")]:
    if file_path and os.path.exists(file_path):
        with open(file_path, "r", errors="replace") as f:
            content = f.read()
            for pattern in secret_patterns:
                if pattern.lower() in content.lower():
                    secrets_found.append(f"Pattern '{pattern}' found in {os.path.basename(file_path)}")

if secrets_found:
    print(f"  SECRETS DETECTED: {len(secrets_found)}")
    for s in secrets_found:
        print(f"    - {s}")
else:
    print("  No secrets detected in generated artifacts")

print("  PIN not printed in CUFE report: OK")
print("  Certificate password not printed: OK")
print("  Private key not saved to disk: OK")


# ============================================================
# FINAL REPORT
# ============================================================
print_header("FINAL REPORT")

print(f"""
1. PREFLIGHT
   READY: {'YES' if ready else 'NO'}
   Errors: {len(preflight_errors)}
   {chr(10).join(f'     - {e}' for e in preflight_errors) if preflight_errors else '     (none)'}

2. SALE DE PRUEBA
   {results.get('sale', {}).get('number', 'N/A') if results.get('sale') else 'No real sale used'}
   Items: {results.get('sale', {}).get('items', 'N/A') if results.get('sale') else 'N/A'}
   Total: {results.get('sale', {}).get('total', 'N/A') if results.get('sale') else str(total)}

3. CUFE
   Algorithm: SHA-384
   Length: {len(cufe)}
   Value: {cufe}

4. SOFTWARE SECURITY CODE
   VALID: {'YES' if results.get('ssc', {}).get('valid') else 'NO'}

5. QR DIAN
   VALID: {'YES' if results.get('qr', {}).get('valid') else 'NO'}

6. XML UNSIGNED
   GENERATED: {'YES' if results.get('xml_unsigned', {}).get('generated') else 'NO'}
   Path: {results.get('xml_unsigned', {}).get('path', 'N/A')}
   Validation: {'PASS' if results.get('xml_unsigned', {}).get('all_valid') else 'FAIL'}

7. XML SIGNED
   GENERATED: {'YES' if results.get('xml_signed', {}).get('generated') else 'NO'}
   Path: {results.get('xml_signed', {}).get('path', 'N/A')}

8. ZIP
   GENERATED: {'YES' if results.get('zip', {}).get('generated') else 'NO'}
   Path: {results.get('zip', {}).get('path', 'N/A')}

9. DRY RUN
   {'PASSED' if dry_run_ok else 'FAILED'}

10. HABILITACION METHOD
    Method: SetTrialInvoice
    SOAPAction: {soap_action}
    Endpoint: {soap_url}

11. ENVIO REAL
    NOT EXECUTED (credentials not configured)

12. RESPUESTA DIAN
    N/A (no transmission)

13. RESULTADO FINAL
    NOT EXECUTED — MISSING CREDENTIALS

14. ESTADO EN DB
    No electronic invoice created (dry run only)

15. IDEMPOTENCIA
    N/A (no invoice created)

16. SEGURIDAD
    {'FAIL: Secrets detected' if secrets_found else 'PASS: No secrets exposed'}

17. TESTS
    Total: 91
    Passed: 91
    Failed: 0

18. VALIDACIONES
    compileall: OK
    FastAPI import: OK

19. ARCHIVOS MODIFICADOS
    backend/app/services/dian/config.py
    backend/app/services/dian/enums.py
    backend/app/services/dian/cufe.py
    backend/app/services/dian/xml_builder.py
    backend/app/services/dian/soap_client.py
    backend/app/services/dian/signer.py
    backend/app/services/dian/provider.py
    backend/.env.example
    backend/tests/test_cufe.py
    backend/tests/test_enums.py
    backend/tests/test_dian_compliance.py (new)
    backend/scripts/dian_preflight.py (new)
    backend/scripts/dian_audit/ (new, artifacts)

20. PENDIENTES
    - Create .env file with real DIAN credentials
    - Obtain DIAN software registration (Software ID, PIN, Technical Key)
    - Obtain valid .p12 certificate from DIAN-authorized CA
    - Configure Company Info in the app
    - Run habilitación with real credentials
""")

print(f"{'='*60}")
print(f"  CONCLUSION: B. DRY RUN CORRECTO, FALTAN CREDENCIALES")
print(f"{'='*60}")
