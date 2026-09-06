import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.dian.validators import (
    validate_invoice_data,
    validate_item,
    validate_company_info,
    validate_resolution,
    validate_tax_totals,
)


def test_validate_invoice_data_valid():
    data = {
        "invoice_number": "1",
        "prefix": "FE",
        "customer_name": "Cliente",
        "items": [{"product_name": "A", "quantity": 1, "unit_price": 100, "subtotal": 100, "tax_rate": 19, "tax_amount": 19}],
        "subtotal": 100,
        "tax_total": 19,
        "total": 119,
    }
    errors = validate_invoice_data(data)
    assert errors == []


def test_validate_invoice_data_missing_fields():
    errors = validate_invoice_data({})
    assert len(errors) == 7
    for field in ["invoice_number", "prefix", "customer_name", "items", "subtotal", "tax_total", "total"]:
        assert any(field in e for e in errors)


def test_validate_invoice_data_empty_items():
    data = {
        "invoice_number": "1",
        "prefix": "FE",
        "customer_name": "Cliente",
        "items": [],
        "subtotal": 0,
        "tax_total": 0,
        "total": 0,
    }
    errors = validate_invoice_data(data)
    assert any("ítem" in e.lower() for e in errors)


def test_validate_invoice_data_negative_totals():
    data = {
        "invoice_number": "1",
        "prefix": "FE",
        "customer_name": "Cliente",
        "items": [],
        "subtotal": -100,
        "tax_total": -19,
        "total": -119,
    }
    errors = validate_invoice_data(data)
    assert any("negativo" in e for e in errors)


def test_validate_item_valid():
    item = {
        "product_name": "Producto",
        "quantity": 2,
        "unit_price": 5000,
        "subtotal": 10000,
        "tax_rate": 19,
        "tax_amount": 1900,
    }
    errors = validate_item(item, 1)
    assert errors == []


def test_validate_item_missing_fields():
    errors = validate_item({}, 1)
    assert len(errors) == 6


def test_validate_item_negative_values():
    item = {
        "product_name": "Producto",
        "quantity": -1,
        "unit_price": 5000,
        "subtotal": 10000,
        "tax_rate": 19,
        "tax_amount": 1900,
    }
    errors = validate_item(item, 1)
    assert any("negativo" in e for e in errors)


def test_validate_item_subtotal_mismatch():
    item = {
        "product_name": "Producto",
        "quantity": 3,
        "unit_price": 5000,
        "subtotal": 99999,
        "tax_rate": 19,
        "tax_amount": 1900,
    }
    errors = validate_item(item, 1)
    assert any("subtotal" in e.lower() and "no coincide" in e for e in errors)


def test_validate_company_info_valid():
    info = {"company_name": "Test S.A.S.", "nit": "900123456", "email": "test@empresa.co"}
    errors = validate_company_info(info)
    assert errors == []


def test_validate_company_info_missing_nit():
    errors = validate_company_info({"company_name": "Test"})
    assert any("nit" in e.lower() for e in errors)


def test_validate_company_info_invalid_email():
    info = {"company_name": "Test", "nit": "900123456", "email": "not-an-email"}
    errors = validate_company_info(info)
    assert any("email" in e.lower() for e in errors)


def test_validate_resolution_valid():
    res = {
        "resolution_number": "12345",
        "resolution_prefix": "FE",
        "resolution_from": "1",
        "resolution_to": "1000000",
    }
    errors = validate_resolution(res)
    assert errors == []


def test_validate_resolution_from_gte_to():
    res = {
        "resolution_number": "12345",
        "resolution_prefix": "FE",
        "resolution_from": "100",
        "resolution_to": "10",
    }
    errors = validate_resolution(res)
    assert any("desde" in e.lower() for e in errors)


def test_validate_resolution_non_numeric():
    res = {
        "resolution_number": "12345",
        "resolution_prefix": "FE",
        "resolution_from": "abc",
        "resolution_to": "xyz",
    }
    errors = validate_resolution(res)
    assert any("numérico" in e.lower() for e in errors)


def test_validate_tax_totals_matching():
    items = [
        {"subtotal": "50000.00", "tax_amount": "9500.00"},
        {"subtotal": "50000.00", "tax_amount": "9500.00"},
    ]
    errors = validate_tax_totals(items, "100000.00", "19000.00", "119000.00")
    assert errors == []


def test_validate_tax_totals_mismatched():
    items = [
        {"subtotal": "50000.00", "tax_amount": "9500.00"},
        {"subtotal": "50000.00", "tax_amount": "9500.00"},
    ]
    errors = validate_tax_totals(items, "99999.00", "19000.00", "119000.00")
    assert len(errors) > 0
    assert any("subtotal" in e.lower() for e in errors)
