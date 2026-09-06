import xml.etree.ElementTree as ET
from decimal import Decimal
from xml.dom import minidom

from .enums import TaxType, TAX_TYPE_NAMES

UBL_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CBC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
EXT_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
STS_NS = "http://www.dian.gov.co/pe/UBL/clac/2.1"

NS_MAP = {
    "": UBL_NS,
    "ext": EXT_NS,
    "cbc": CBC_NS,
    "cac": CAC_NS,
    "ds": DS_NS,
    "sts": STS_NS,
}


def _register_namespaces() -> None:
    for prefix, uri in NS_MAP.items():
        if prefix:
            ET.register_namespace(prefix, uri)
        else:
            ET.register_namespace("", uri)


def _add_text(parent: ET.Element, tag: str, text: str, ns: str = "cbc") -> ET.Element:
    prefix_ns = NS_MAP.get(ns, CBC_NS)
    el = ET.SubElement(parent, f"{{{prefix_ns}}}{tag}")
    el.text = str(text)
    return el


def _decimal_str(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


class DianInvoiceXmlBuilder:
    """Constructor de XML UBL 2.1 para facturación electrónica DIAN.

    Genera un XML válido según el Anexo Técnico v1.9, incluyendo:
    - ext:UBLExtensions con DianExtensions (InvoiceControl, InvoiceSource,
      SoftwareProvider, SoftwareSecurityCode, AuthorizationProvider, QRCode)
    - ProfileExecutionID para ambiente
    - Codigos numéricos para InvoiceTypeCode, IdentificationType, etc.
    """

    def __init__(
        self,
        *,
        invoice_number: str,
        prefix: str,
        issue_date: str,
        issue_time: str,
        invoice_type_code: str = "01",
        document_currency_code: str = "COP",
        customer_id_type: str = "13",
        customer_id: str = "",
        customer_name: str = "",
        customer_address: str = "",
        customer_email: str = "",
        supplier_name: str = "",
        supplier_nit: str = "",
        supplier_dv: str = "",
        supplier_address: str = "",
        supplier_municipality: str = "",
        supplier_department: str = "",
        supplier_country: str = "CO",
        supplier_phone: str = "",
        supplier_email: str = "",
        supplier_regime: str = "O-47",
        resolution_number: str = "",
        resolution_prefix: str = "FE",
        resolution_from: str = "",
        resolution_to: str = "",
        resolution_start_date: str = "",
        resolution_end_date: str = "",
        payment_form: str = "1",
        payment_method: str = "10",
        payment_due_date: str = "",
        items: list[dict] | None = None,
        subtotal: Decimal = Decimal("0"),
        tax_total: Decimal = Decimal("0"),
        total: Decimal = Decimal("0"),
        allowance_total: Decimal = Decimal("0"),
        environment_code: str = "2",
        software_id: str = "",
        software_provider_nit: str = "",
        software_security_code: str = "",
        qr_url: str = "",
        cufe: str = "",
    ):
        self.invoice_number = invoice_number
        self.prefix = prefix
        self.issue_date = issue_date
        self.issue_time = issue_time
        self.invoice_type_code = invoice_type_code
        self.document_currency_code = document_currency_code
        self.customer_id_type = customer_id_type
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.customer_address = customer_address
        self.customer_email = customer_email
        self.supplier_name = supplier_name
        self.supplier_nit = supplier_nit
        self.supplier_dv = supplier_dv
        self.supplier_address = supplier_address
        self.supplier_municipality = supplier_municipality
        self.supplier_department = supplier_department
        self.supplier_country = supplier_country
        self.supplier_phone = supplier_phone
        self.supplier_email = supplier_email
        self.supplier_regime = supplier_regime
        self.resolution_number = resolution_number
        self.resolution_prefix = resolution_prefix
        self.resolution_from = resolution_from
        self.resolution_to = resolution_to
        self.resolution_start_date = resolution_start_date
        self.resolution_end_date = resolution_end_date
        self.payment_form = payment_form
        self.payment_method = payment_method
        self.payment_due_date = payment_due_date
        self.items = items or []
        self.subtotal = subtotal
        self.tax_total = tax_total
        self.total = total
        self.allowance_total = allowance_total
        self.environment_code = environment_code
        self.software_id = software_id
        self.software_provider_nit = software_provider_nit
        self.software_security_code = software_security_code
        self.qr_url = qr_url
        self.cufe = cufe

    def build(self) -> str:
        _register_namespaces()
        root = ET.Element(f"{{{UBL_NS}}}Invoice")

        self._add_ubl_extensions(root)
        self._add_header(root)
        self._add_supplier_party(root)
        self._add_customer_party(root)
        self._add_payment_means(root)
        self._add_tax_total(root)
        self._add_legal_monetary_total(root)
        self._add_invoice_lines(root)

        xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
        dom = minidom.parseString(xml_str)
        pretty = dom.toprettyxml(indent="  ", encoding=None)
        lines = pretty.split("\n")
        if lines and lines[0].startswith("<?xml"):
            lines = lines[1:]
        result = "\n".join(lines)
        if not result.startswith("<?xml"):
            result = '<?xml version="1.0" encoding="UTF-8"?>\n' + result
        return result

    def build_bytes(self) -> bytes:
        return self.build().encode("utf-8")

    def _add_ubl_extensions(self, root: ET.Element) -> None:
        ubl_ext = ET.SubElement(root, f"{{{EXT_NS}}}UBLExtensions")

        ext1 = ET.SubElement(ubl_ext, f"{{{EXT_NS}}}UBLExtension")
        ext1_content = ET.SubElement(ext1, f"{{{EXT_NS}}}ExtensionContent")

        dian_ext = ET.SubElement(ext1_content, f"{{{STS_NS}}}DianExtensions")

        self._add_invoice_control(dian_ext)
        self._add_invoice_source(dian_ext)
        self._add_software_provider(dian_ext)
        self._add_software_security_code(dian_ext)
        self._add_authorization_provider(dian_ext)
        self._add_qr_code(dian_ext)

        ext2 = ET.SubElement(ubl_ext, f"{{{EXT_NS}}}UBLExtension")
        ET.SubElement(ext2, f"{{{EXT_NS}}}ExtensionContent")

    def _add_invoice_control(self, parent: ET.Element) -> None:
        ic = ET.SubElement(parent, f"{{{STS_NS}}}InvoiceControl")
        _add_text(ic, "InvoiceAuthorization", self.resolution_number, "sts")

        ap = ET.SubElement(ic, f"{{{STS_NS}}}AuthorizationPeriod")
        _add_text(ap, "StartDate", self.resolution_start_date, "sts")
        _add_text(ap, "EndDate", self.resolution_end_date, "sts")

        ai = ET.SubElement(ic, f"{{{STS_NS}}}AuthorizedInvoices")
        _add_text(ai, "Prefix", self.resolution_prefix, "sts")
        _add_text(ai, "From", self.resolution_from, "sts")
        _add_text(ai, "To", self.resolution_to, "sts")

    def _add_invoice_source(self, parent: ET.Element) -> None:
        inv_src = ET.SubElement(parent, f"{{{STS_NS}}}InvoiceSource")
        _add_text(inv_src, "IdentificationCode", self.supplier_country, "sts")

    def _add_software_provider(self, parent: ET.Element) -> None:
        sp = ET.SubElement(parent, f"{{{STS_NS}}}SoftwareProvider")
        _add_text(sp, "ProviderID", self.software_provider_nit, "sts")
        _add_text(sp, "SoftwareID", self.software_id, "sts")

    def _add_software_security_code(self, parent: ET.Element) -> None:
        _add_text(parent, "SoftwareSecurityCode", self.software_security_code, "sts")

    def _add_authorization_provider(self, parent: ET.Element) -> None:
        ap = ET.SubElement(parent, f"{{{STS_NS}}}AuthorizationProvider")
        _add_text(ap, "AuthorizationProviderID", "800197268", "sts")

    def _add_qr_code(self, parent: ET.Element) -> None:
        _add_text(parent, "QRCode", self.qr_url, "sts")

    def _add_header(self, root: ET.Element) -> None:
        _add_text(root, "UBLVersionID", "2.1")
        _add_text(root, "CustomizationID", "10")
        _add_text(root, "ProfileID", "DIAN:2.1:FacturaElectronica:Base")
        _add_text(root, "ID", f"{self.prefix}{self.invoice_number}")
        _add_text(root, "IssueDate", self.issue_date)
        _add_text(root, "IssueTime", self.issue_time)
        _add_text(root, "InvoiceTypeCode", self.invoice_type_code)

        if self.cufe:
            _add_text(root, "UUID", self.cufe)

        _add_text(root, "DocumentCurrencyCode", self.document_currency_code)
        _add_text(root, "ProfileExecutionID", self.environment_code)

        if self.resolution_start_date and self.resolution_end_date:
            period = ET.SubElement(root, f"{{{UBL_NS}}}InvoicePeriod")
            _add_text(period, "StartDate", self.resolution_start_date)
            _add_text(period, "EndDate", self.resolution_end_date)

    def _add_supplier_party(self, root: ET.Element) -> None:
        party = ET.SubElement(root, f"{{{UBL_NS}}}AccountingSupplierParty")
        p = ET.SubElement(party, f"{{{CAC_NS}}}Party")

        endpoint = ET.SubElement(p, f"{{{CAC_NS}}}EndpointID")
        endpoint.set("schemeID", "9")
        endpoint.set("schemeName", "31")
        endpoint.set("schemeAgencyID", "195")
        endpoint.set("schemeAgencyName", "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)")
        endpoint.text = self.supplier_nit

        party_name = ET.SubElement(p, f"{{{CAC_NS}}}PartyName")
        _add_text(party_name, "Name", self.supplier_name)

        postal = ET.SubElement(p, f"{{{CAC_NS}}}PostalAddress")
        _add_text(postal, "ID", "0")
        if self.supplier_municipality:
            _add_text(postal, "CityName", self.supplier_municipality)
        if self.supplier_department:
            _add_text(postal, "CountrySubentity", self.supplier_department)
        country_el = ET.SubElement(postal, f"{{{CAC_NS}}}Country")
        _add_text(country_el, "IdentificationCode", self.supplier_country)

        party_tax = ET.SubElement(p, f"{{{CAC_NS}}}PartyTaxScheme")
        _add_text(party_tax, "RegistrationName", self.supplier_name)
        company_id = ET.SubElement(party_tax, f"{{{CBC_NS}}}CompanyID")
        company_id.set("schemeAgencyID", "195")
        company_id.set("schemeAgencyName", "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)")
        company_id.set("schemeID", self.supplier_dv or "0")
        company_id.text = self.supplier_nit

        tax_scheme = ET.SubElement(party_tax, f"{{{CAC_NS}}}TaxScheme")
        _add_text(tax_scheme, "ID", "01")

        party_legal = ET.SubElement(p, f"{{{CAC_NS}}}PartyLegalEntity")
        _add_text(party_legal, "RegistrationName", self.supplier_name)
        _add_text(party_legal, "RegistrationAddress", self.supplier_address or "")

        contact = ET.SubElement(p, f"{{{CAC_NS}}}Contact")
        _add_text(contact, "Telephone", self.supplier_phone or "")
        _add_text(contact, "ElectronicMail", self.supplier_email or "")

    def _add_customer_party(self, root: ET.Element) -> None:
        party = ET.SubElement(root, f"{{{UBL_NS}}}AccountingCustomerParty")
        p = ET.SubElement(party, f"{{{CAC_NS}}}Party")

        endpoint = ET.SubElement(p, f"{{{CAC_NS}}}EndpointID")
        endpoint.set("schemeID", self.customer_id_type)
        endpoint.text = self.customer_id

        if self.customer_name:
            party_name = ET.SubElement(p, f"{{{CAC_NS}}}PartyName")
            _add_text(party_name, "Name", self.customer_name)

        if self.customer_address:
            postal = ET.SubElement(p, f"{{{CAC_NS}}}PostalAddress")
            _add_text(postal, "StreetName", self.customer_address)
            country_el = ET.SubElement(postal, f"{{{CAC_NS}}}Country")
            _add_text(country_el, "IdentificationCode", "CO")

        party_legal = ET.SubElement(p, f"{{{CAC_NS}}}PartyLegalEntity")
        _add_text(party_legal, "RegistrationName", self.customer_name)

        contact = ET.SubElement(p, f"{{{CAC_NS}}}Contact")
        if self.customer_email:
            _add_text(contact, "ElectronicMail", self.customer_email)

    def _add_payment_means(self, root: ET.Element) -> None:
        pm = ET.SubElement(root, f"{{{UBL_NS}}}PaymentMeans")
        _add_text(pm, "PaymentMeansCode", self.payment_method)
        if self.payment_due_date:
            _add_text(pm, "PaymentDueDate", self.payment_due_date)

        pt = ET.SubElement(root, f"{{{UBL_NS}}}PaymentTerms")
        _add_text(pt, "Note", "Contado" if self.payment_form == "1" else "Crédito")

    def _add_tax_total(self, root: ET.Element) -> None:
        if self.tax_total == Decimal("0") and not self.items:
            return

        tax_total_el = ET.SubElement(root, f"{{{UBL_NS}}}TaxTotal")
        _add_text(tax_total_el, "TaxAmount", _decimal_str(self.tax_total), "cbc")

        for item in self.items:
            tax_sub = ET.SubElement(tax_total_el, f"{{{CAC_NS}}}TaxSubtotal")
            _add_text(tax_sub, "TaxableAmount", _decimal_str(Decimal(str(item.get("subtotal", "0.00")))), "cbc")
            _add_text(tax_sub, "TaxAmount", _decimal_str(Decimal(str(item.get("tax_amount", "0.00")))), "cbc")
            tax_cat = ET.SubElement(tax_sub, f"{{{CAC_NS}}}TaxCategory")
            tax_rate_el = ET.SubElement(tax_cat, f"{{{CBC_NS}}}Percent")
            tax_rate_el.text = str(item.get("tax_rate", "0"))
            tax_scheme = ET.SubElement(tax_cat, f"{{{CAC_NS}}}TaxScheme")
            _add_text(tax_scheme, "ID", item.get("tax_type", TaxType.IVA.value), "cbc")
            tax_name = TAX_TYPE_NAMES.get(
                TaxType(item.get("tax_type", TaxType.IVA.value)),
                item.get("tax_type_name", "IVA"),
            )
            _add_text(tax_scheme, "Name", tax_name, "cbc")

    def _add_legal_monetary_total(self, root: ET.Element) -> None:
        lmt = ET.SubElement(root, f"{{{UBL_NS}}}LegalMonetaryTotal")
        _add_text(lmt, "LineExtensionAmount", _decimal_str(self.subtotal), "cbc")
        _add_text(lmt, "TaxExclusiveAmount", _decimal_str(self.subtotal), "cbc")
        _add_text(lmt, "TaxInclusiveAmount", _decimal_str(self.total), "cbc")

        if self.allowance_total > Decimal("0"):
            _add_text(lmt, "AllowanceTotalAmount", _decimal_str(self.allowance_total), "cbc")

        _add_text(lmt, "PayableAmount", _decimal_str(self.total), "cbc")

    def _add_invoice_lines(self, root: ET.Element) -> None:
        for idx, item in enumerate(self.items, start=1):
            line = ET.SubElement(root, f"{{{UBL_NS}}}InvoiceLine")
            _add_text(line, "ID", str(idx))

            invoiced_qty = ET.SubElement(line, f"{{{CBC_NS}}}InvoicedQuantity")
            invoiced_qty.set("unitCode", item.get("unit_code", "94"))
            invoiced_qty.text = str(Decimal(str(item.get("quantity", "1"))))

            _add_text(line, "LineExtensionAmount", _decimal_str(Decimal(str(item.get("subtotal", "0.00")))), "cbc")

            item_el = ET.SubElement(line, f"{{{CAC_NS}}}Item")
            _add_text(item_el, "Description", item.get("product_name", ""))
            _add_text(item_el, "Name", item.get("product_name", ""))

            sellers_id = ET.SubElement(item_el, f"{{{CAC_NS}}}SellersItemIdentification")
            _add_text(sellers_id, "ID", item.get("sku", "001"))

            item_tax_total = ET.SubElement(item_el, f"{{{UBL_NS}}}TaxTotal")
            _add_text(item_tax_total, "TaxAmount", _decimal_str(Decimal(str(item.get("tax_amount", "0.00")))), "cbc")
            item_tax_sub = ET.SubElement(item_tax_total, f"{{{CAC_NS}}}TaxSubtotal")
            _add_text(item_tax_sub, "TaxableAmount", _decimal_str(Decimal(str(item.get("subtotal", "0.00")))), "cbc")
            _add_text(item_tax_sub, "TaxAmount", _decimal_str(Decimal(str(item.get("tax_amount", "0.00")))), "cbc")
            item_tax_cat = ET.SubElement(item_tax_sub, f"{{{CAC_NS}}}TaxCategory")
            item_tax_pct = ET.SubElement(item_tax_cat, f"{{{CBC_NS}}}Percent")
            item_tax_pct.text = str(item.get("tax_rate", "0"))
            item_tax_scheme = ET.SubElement(item_tax_cat, f"{{{CAC_NS}}}TaxScheme")
            _add_text(item_tax_scheme, "ID", item.get("tax_type", TaxType.IVA.value), "cbc")

            price = ET.SubElement(line, f"{{{CAC_NS}}}Price")
            _add_text(price, "PriceAmount", _decimal_str(Decimal(str(item.get("unit_price", "0.00")))), "cbc")
