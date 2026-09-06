import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.dian.enums import (
    InvoiceStatus,
    TaxType,
    PaymentForm,
    DIANStatusCode,
    TAX_TYPE_NAMES,
    PAYMENT_FORM_NAMES,
)


def test_invoice_status_values():
    expected = {"DRAFT", "GENERATED", "SIGNED", "SENDING", "SENT", "ACCEPTED", "REJECTED", "ERROR", "PENDING"}
    actual = {s.value for s in InvoiceStatus}
    assert actual == expected


def test_tax_type_values():
    assert TaxType.IVA.value == "01"
    assert TaxType.IC.value == "02"
    assert TaxType.ICA.value == "03"
    assert TaxType.INC.value == "04"
    assert TaxType.RETE_IVA.value == "05"
    assert TaxType.RETE_RENTA.value == "06"
    assert TaxType.RETE_ICA.value == "07"


def test_tax_type_names():
    assert TAX_TYPE_NAMES[TaxType.IVA] == "IVA"
    assert TAX_TYPE_NAMES[TaxType.IC] == "IC"
    assert TAX_TYPE_NAMES[TaxType.ICA] == "ICA"
    assert TAX_TYPE_NAMES[TaxType.INC] == "INC"


def test_payment_form_values():
    assert PaymentForm.CONTADO.value == "1"
    assert PaymentForm.CREDITO.value == "2"


def test_payment_form_names():
    assert PAYMENT_FORM_NAMES[PaymentForm.CONTADO] == "Contado"
    assert PAYMENT_FORM_NAMES[PaymentForm.CREDITO] == "Crédito"


def test_dian_status_code_messages():
    assert DIANStatusCode.get_message("00") == "Aceptado"
    assert DIANStatusCode.get_message("01") == "Aceptado con observaciones"
    assert DIANStatusCode.get_message("02") == "Rechazado"
    assert DIANStatusCode.get_message("03") == "Firma inválida"
    assert DIANStatusCode.get_message("04") == "Documento en proceso"
    assert DIANStatusCode.get_message("09") == "XML inválido"


def test_dian_status_code_unknown():
    msg = DIANStatusCode.get_message("999")
    assert "desconocido" in msg.lower()
    assert "999" in msg
