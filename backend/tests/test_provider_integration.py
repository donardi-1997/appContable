import sys
import os
import json
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app.services.mock_provider import MockElectronicInvoiceProvider
from app.services.invoice_provider import InvoiceItemData


@pytest.fixture
def provider():
    return MockElectronicInvoiceProvider()


@pytest.fixture
def sample_items():
    return [
        InvoiceItemData(
            product_name="Producto A",
            quantity=Decimal("10"),
            unit_price=Decimal("5000.00"),
            subtotal=Decimal("50000.00"),
            tax_rate=Decimal("19.00"),
            tax_amount=Decimal("9500.00"),
            tax_type="IVA",
        ),
        InvoiceItemData(
            product_name="Producto B",
            quantity=Decimal("5"),
            unit_price=Decimal("10000.00"),
            subtotal=Decimal("50000.00"),
            tax_rate=Decimal("19.00"),
            tax_amount=Decimal("9500.00"),
            tax_type="IVA",
        ),
    ]


@pytest.fixture
def invoice_result(provider, sample_items):
    return provider.create_invoice(
        invoice_number="1",
        prefix="FE",
        customer_name="Cliente Test",
        customer_document_type="CC",
        customer_document_number="123456789",
        customer_email="test@test.com",
        customer_address="Calle 123",
        customer_phone="3001234567",
        items=sample_items,
        subtotal=Decimal("100000.00"),
        tax_total=Decimal("19000.00"),
        total=Decimal("119000.00"),
        environment="sandbox",
    )


def test_mock_provider_create_and_get_xml(provider, sample_items):
    result = provider.create_invoice(
        invoice_number="1",
        prefix="FE",
        customer_name="Cliente Test",
        customer_document_type="CC",
        customer_document_number="123456789",
        customer_email=None,
        customer_address=None,
        customer_phone=None,
        items=sample_items,
        subtotal=Decimal("100000.00"),
        tax_total=Decimal("19000.00"),
        total=Decimal("119000.00"),
        environment="sandbox",
    )
    xml = provider.get_xml(result.provider_reference)
    assert xml is not None
    assert '<?xml' in xml


def test_mock_provider_create_and_get_cufe(provider, sample_items):
    result = provider.create_invoice(
        invoice_number="1",
        prefix="FE",
        customer_name="Cliente Test",
        customer_document_type="CC",
        customer_document_number="123456789",
        customer_email=None,
        customer_address=None,
        customer_phone=None,
        items=sample_items,
        subtotal=Decimal("100000.00"),
        tax_total=Decimal("19000.00"),
        total=Decimal("119000.00"),
        environment="sandbox",
    )
    assert result.cufe is not None
    assert len(result.cufe) == 64


def test_provider_result_serialization(invoice_result):
    d = {
        "success": invoice_result.success,
        "provider": invoice_result.provider,
        "provider_reference": invoice_result.provider_reference,
        "cufe": invoice_result.cufe,
        "status": invoice_result.status,
        "error_message": invoice_result.error_message,
    }
    json_str = json.dumps(d)
    loaded = json.loads(json_str)
    assert loaded["success"] is True
    assert loaded["provider"] == "mock"
    assert loaded["provider_reference"].startswith("MOCK-")
    assert loaded["status"] == "ACCEPTED"
