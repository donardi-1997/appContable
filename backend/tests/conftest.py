import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest


@pytest.fixture
def valid_invoice_data():
    return {
        "invoice_number": "1",
        "prefix": "FE",
        "customer_name": "Cliente Test S.A.S.",
        "customer_id_type": "NIT",
        "customer_id": "900123456",
        "items": [],
        "subtotal": Decimal("100000.00"),
        "tax_total": Decimal("19000.00"),
        "total": Decimal("119000.00"),
    }


@pytest.fixture
def valid_items():
    return [
        {
            "product_name": "Producto A",
            "quantity": Decimal("10"),
            "unit_price": Decimal("5000.00"),
            "subtotal": Decimal("50000.00"),
            "tax_rate": Decimal("19.00"),
            "tax_amount": Decimal("9500.00"),
            "tax_type": "01",
            "unit_code": "94",
            "sku": "PA-001",
        },
        {
            "product_name": "Producto B",
            "quantity": Decimal("5"),
            "unit_price": Decimal("10000.00"),
            "subtotal": Decimal("50000.00"),
            "tax_rate": Decimal("19.00"),
            "tax_amount": Decimal("9500.00"),
            "tax_type": "01",
            "unit_code": "94",
            "sku": "PB-001",
        },
    ]


@pytest.fixture
def xml_builder(valid_items):
    from app.services.dian.xml_builder import DianInvoiceXmlBuilder

    return DianInvoiceXmlBuilder(
        invoice_number="1",
        prefix="FE",
        issue_date="2026-01-15",
        issue_time="12:00:00",
        customer_id_type="NIT",
        customer_id="900123456",
        customer_name="Cliente Test S.A.S.",
        supplier_name="Empresa Test Ltda",
        supplier_nit="900987654",
        supplier_dv="1",
        supplier_municipality="Bogota",
        supplier_department="Bogota",
        resolution_number="1234567890",
        resolution_prefix="FE",
        resolution_from="1",
        resolution_to="1000000",
        resolution_start_date="2026-01-01",
        resolution_end_date="2026-12-31",
        items=valid_items,
        subtotal=Decimal("100000.00"),
        tax_total=Decimal("19000.00"),
        total=Decimal("119000.00"),
    )
