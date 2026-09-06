import sys
import os
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


import pytest


def test_create_invoice_sandbox(provider, sample_items):
    result = provider.create_invoice(
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
    assert result.success is True
    assert result.status == "ACCEPTED"


def test_create_invoice_not_sandbox(provider, sample_items):
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
        environment="produccion",
    )
    assert result.success is False
    assert "sandbox" in result.error_message.lower()


def test_get_invoice_status(provider):
    status = provider.get_invoice_status("MOCK-ABC123")
    assert status.status == "ACCEPTED"


def test_provider_reference_starts_with_mock(provider, sample_items):
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
    assert result.provider_reference.startswith("MOCK-")


def test_invoice_result_has_cufe(provider, sample_items):
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
