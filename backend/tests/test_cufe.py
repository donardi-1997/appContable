import re
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.dian.cufe import calculate_cufe, calculate_software_security_code, calculate_qr_url


CUFE_96_HEX = re.compile(r"^[0-9A-F]{96}$")


BASE_KWARGS = dict(
    document_type="01",
    invoice_number="FE00000001",
    issue_date="2026-01-15",
    issue_time="12:00:00-05:00",
    line_extension_amount=Decimal("100000.00"),
    tax_totals={"01": Decimal("19000.00"), "04": Decimal("0.00"), "03": Decimal("0.00")},
    payable_amount=Decimal("119000.00"),
    supplier_nit="900123456",
    customer_id="900654321",
    technical_key="fc8eac425c29d8c3fc8eac420b26cf00668ea99812ab8",
    environment_code="2",
)


def test_returns_96_char_uppercase_hex():
    cufe = calculate_cufe(**BASE_KWARGS)
    assert len(cufe) == 96
    assert CUFE_96_HEX.match(cufe), f"CUFE is not 96-char uppercase hex: {cufe}"


def test_deterministic_same_inputs():
    cufe1 = calculate_cufe(**BASE_KWARGS)
    cufe2 = calculate_cufe(**BASE_KWARGS)
    assert cufe1 == cufe2


def test_different_invoice_numbers():
    args1 = {**BASE_KWARGS, "invoice_number": "FE00000001"}
    args2 = {**BASE_KWARGS, "invoice_number": "FE00000002"}
    assert calculate_cufe(**args1) != calculate_cufe(**args2)


def test_different_technical_keys():
    args1 = {**BASE_KWARGS, "technical_key": "KEY123456"}
    args2 = {**BASE_KWARGS, "technical_key": "KEY654321"}
    assert calculate_cufe(**args1) != calculate_cufe(**args2)


def test_zero_tax_amounts():
    args = {
        **BASE_KWARGS,
        "line_extension_amount": Decimal("50000.00"),
        "tax_totals": {"01": Decimal("0.00"), "04": Decimal("0.00"), "03": Decimal("0.00")},
        "payable_amount": Decimal("50000.00"),
    }
    cufe = calculate_cufe(**args)
    assert len(cufe) == 96
    assert CUFE_96_HEX.match(cufe)


def test_different_environments():
    args1 = {**BASE_KWARGS, "environment_code": "1"}
    args2 = {**BASE_KWARGS, "environment_code": "2"}
    assert calculate_cufe(**args1) != calculate_cufe(**args2)


def test_software_security_code():
    code = calculate_software_security_code(
        software_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        pin="12345",
        document_number="FE00000001",
    )
    assert len(code) == 96
    assert CUFE_96_HEX.match(code)


def test_software_security_code_deterministic():
    code1 = calculate_software_security_code("SID", "PIN", "NUM")
    code2 = calculate_software_security_code("SID", "PIN", "NUM")
    assert code1 == code2


def test_software_security_code_different_inputs():
    code1 = calculate_software_security_code("SID1", "PIN", "NUM")
    code2 = calculate_software_security_code("SID2", "PIN", "NUM")
    assert code1 != code2


def test_qr_url_format():
    cufe = calculate_cufe(**BASE_KWARGS)
    url = calculate_qr_url(cufe)
    assert url.startswith("https://catalogovpfe.dian.gov.co/document/searchqr?documentkey=")
    assert cufe in url
