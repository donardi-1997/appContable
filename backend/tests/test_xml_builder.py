import re
import sys
import os
import xml.etree.ElementTree as ET
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.dian.xml_builder import DianInvoiceXmlBuilder, UBL_NS, CBC_NS


def test_build_returns_valid_xml(xml_builder):
    xml_str = xml_builder.build()
    assert xml_str.startswith("<?xml")
    ET.fromstring(xml_str)


def test_ubl_namespaces(xml_builder):
    xml_str = xml_builder.build()
    root = ET.fromstring(xml_str)
    assert root.tag == f"{{{UBL_NS}}}Invoice"


def test_invoice_id(xml_builder):
    xml_str = xml_builder.build()
    root = ET.fromstring(xml_str)
    id_el = root.find(f"{{{CBC_NS}}}ID")
    assert id_el is not None
    assert id_el.text == "FE1"


def test_supplier_party(xml_builder):
    xml_str = xml_builder.build()
    root = ET.fromstring(xml_str)
    assert "900987654" in xml_str
    supplier = root.find(f"{{{UBL_NS}}}AccountingSupplierParty")
    assert supplier is not None


def test_customer_party(xml_builder):
    xml_str = xml_builder.build()
    root = ET.fromstring(xml_str)
    customer = root.find(f"{{{UBL_NS}}}AccountingCustomerParty")
    assert customer is not None
    assert "Cliente Test S.A.S." in xml_str


def test_invoice_lines(xml_builder):
    xml_str = xml_builder.build()
    root = ET.fromstring(xml_str)
    lines = root.findall(f"{{{UBL_NS}}}InvoiceLine")
    assert len(lines) == 2


def test_tax_total(xml_builder):
    xml_str = xml_builder.build()
    root = ET.fromstring(xml_str)
    tax_total = root.find(f"{{{UBL_NS}}}TaxTotal")
    assert tax_total is not None


def test_monetary_total(xml_builder):
    xml_str = xml_builder.build()
    root = ET.fromstring(xml_str)
    lmt = root.find(f"{{{UBL_NS}}}LegalMonetaryTotal")
    assert lmt is not None
    line_ext = lmt.find(f"{{{CBC_NS}}}LineExtensionAmount")
    assert line_ext is not None
    assert line_ext.text == "100000.00"
    tax_incl = lmt.find(f"{{{CBC_NS}}}TaxInclusiveAmount")
    assert tax_incl is not None
    assert tax_incl.text == "119000.00"


def test_build_bytes(xml_builder):
    result = xml_builder.build_bytes()
    assert isinstance(result, bytes)
    assert b"<?xml" in result
