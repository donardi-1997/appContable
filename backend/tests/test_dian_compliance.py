import re
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.dian.cufe import calculate_cufe, calculate_software_security_code, calculate_qr_url
from app.services.dian.xml_builder import DianInvoiceXmlBuilder
from app.services.dian.config import DIANConfig
from app.services.dian.enums import DocumentType, CUFE_DOCUMENTS, CUDE_DOCUMENTS, CUFE_TAX_ORDER, TaxType


CUFE_96_HEX = re.compile(r"^[0-9A-F]{96}$")


class TestCufeCompliance:
    """Tests de cumplimiento del CUFE según Anexo Técnico v1.9."""

    def test_cufe_is_96_hex_uppercase(self):
        cufe = calculate_cufe(
            document_type="01",
            invoice_number="FE00000001",
            issue_date="2026-01-15",
            issue_time="12:00:00-05:00",
            line_extension_amount=Decimal("100000.00"),
            tax_totals={"01": Decimal("19000.00"), "04": Decimal("0.00"), "03": Decimal("0.00")},
            payable_amount=Decimal("119000.00"),
            supplier_nit="900123456",
            customer_id="900654321",
            technical_key="testkey123",
            environment_code="2",
        )
        assert len(cufe) == 96
        assert CUFE_96_HEX.match(cufe)

    def test_cufe_concatenation_formula_15_fields(self):
        """Verifica que el CUFE usa los 15 campos oficiales en el orden correcto."""
        from app.services.dian.cufe import _truncate

        cufe1 = calculate_cufe(
            document_type="01",
            invoice_number="FE00000001",
            issue_date="2026-01-15",
            issue_time="12:00:00-05:00",
            line_extension_amount=Decimal("100000.00"),
            tax_totals={"01": Decimal("19000.00"), "04": Decimal("0.00"), "03": Decimal("0.00")},
            payable_amount=Decimal("119000.00"),
            supplier_nit="900123456",
            customer_id="900654321",
            technical_key="testkey123",
            environment_code="2",
        )

        expected_concat = (
            "FE00000001"
            "2026-01-15"
            "12:00:00-05:00"
            "100000.00"
            "01" "19000.00"
            "04" "0.00"
            "03" "0.00"
            "119000.00"
            "900123456"
            "900654321"
            "testkey123"
            "2"
        )
        import hashlib
        expected_cufe = hashlib.sha384(expected_concat.encode("utf-8")).hexdigest().upper()
        assert cufe1 == expected_cufe

    def test_cufe_tax_codes_fixed_order(self):
        """Los impuestos siempre van en orden: IVA(01), INC(04), ICA(03)."""
        assert CUFE_TAX_ORDER == (TaxType.IVA, TaxType.INC, TaxType.ICA)

    def test_cufe_uses_technical_key_for_invoices(self):
        """Facturas de venta usan technicalKey (clave técnica)."""
        cufe_tech = calculate_cufe(
            document_type="01",
            invoice_number="FE00000001",
            issue_date="2026-01-15",
            issue_time="12:00:00-05:00",
            line_extension_amount=Decimal("100000.00"),
            tax_totals={"01": Decimal("19000.00"), "04": Decimal("0.00"), "03": Decimal("0.00")},
            payable_amount=Decimal("119000.00"),
            supplier_nit="900123456",
            customer_id="900654321",
            technical_key="my_technical_key_123",
            environment_code="2",
        )
        cufe_pin = calculate_cufe(
            document_type="01",
            invoice_number="FE00000001",
            issue_date="2026-01-15",
            issue_time="12:00:00-05:00",
            line_extension_amount=Decimal("100000.00"),
            tax_totals={"01": Decimal("19000.00"), "04": Decimal("0.00"), "03": Decimal("0.00")},
            payable_amount=Decimal("119000.00"),
            supplier_nit="900123456",
            customer_id="900654321",
            technical_key="different_pin",
            environment_code="2",
        )
        assert cufe_tech != cufe_pin

    def test_cufe_document_types_classification(self):
        """Verificar clasificación correcta CUFE vs CUDE."""
        assert DocumentType.FACTURA_VENTA in CUFE_DOCUMENTS
        assert DocumentType.FACTURA_EXPORTACION in CUFE_DOCUMENTS
        assert DocumentType.FACTURA_TIPO_04 in CUFE_DOCUMENTS
        assert DocumentType.NOTA_CREDITO in CUDE_DOCUMENTS
        assert DocumentType.NOTA_DEBITO in CUDE_DOCUMENTS
        assert DocumentType.POS in CUDE_DOCUMENTS

    def test_cufe_truncation_not_rounding(self):
        """Los valores monetarios se TRUNCAN (no redondean)."""
        from app.services.dian.cufe import _truncate
        assert _truncate(Decimal("100.009")) == "100.00"
        assert _truncate(Decimal("100.005")) == "100.00"
        assert _truncate(Decimal("100.099")) == "100.09"

    def test_cufe_empty_tax_totals(self):
        """Impuestos ausentes contribuyen con 0.00."""
        cufe = calculate_cufe(
            document_type="01",
            invoice_number="FE00000001",
            issue_date="2026-01-15",
            issue_time="12:00:00-05:00",
            line_extension_amount=Decimal("50000.00"),
            tax_totals={},
            payable_amount=Decimal("50000.00"),
            supplier_nit="900123456",
            customer_id="900654321",
            technical_key="testkey",
            environment_code="2",
        )
        assert len(cufe) == 96


class TestSoftwareSecurityCode:
    """Tests del SoftwareSecurityCode según Anexo Técnico v1.9."""

    def test_formula_is_sha384_software_id_pin_number(self):
        import hashlib
        software_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        pin = "12345"
        doc_number = "FE00000001"

        expected = hashlib.sha384(
            (software_id + pin + doc_number).encode("utf-8")
        ).hexdigest().upper()

        actual = calculate_software_security_code(software_id, pin, doc_number)
        assert actual == expected

    def test_is_96_hex(self):
        code = calculate_software_security_code("SID", "PIN", "NUM")
        assert len(code) == 96
        assert CUFE_96_HEX.match(code)


class TestQrUrl:
    """Tests del QR URL según Anexo Técnico v1.9."""

    def test_url_format(self):
        url = calculate_qr_url("ABC123")
        assert url == "https://catalogovpfe.dian.gov.co/document/searchqr?documentkey=ABC123"

    def test_url_contains_cufe(self):
        cufe = "A" * 96
        url = calculate_qr_url(cufe)
        assert cufe in url


class TestXmlBuilderCompliance:
    """Tests de cumplimiento del XML builder contra Anexo Técnico v1.9."""

    def _build_sample_xml(self, **kwargs):
        defaults = dict(
            invoice_number="00000001",
            prefix="FE",
            issue_date="2026-01-15",
            issue_time="12:00:00-05:00",
            invoice_type_code="01",
            customer_id_type="13",
            customer_id="1234567890",
            customer_name="Cliente Test",
            supplier_name="900123456",
            supplier_nit="900123456",
            supplier_dv="0",
            resolution_number="18764003560527",
            resolution_prefix="FE",
            resolution_from="1",
            resolution_to="1000000",
            resolution_start_date="2024-01-01",
            resolution_end_date="2030-12-31",
            environment_code="2",
            software_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            software_provider_nit="900123456",
            software_security_code="ABC123",
            qr_url="https://catalogovpfe.dian.gov.co/document/searchqr?documentkey=ABC",
            cufe="A" * 96,
            items=[{
                "product_name": "Test Product",
                "quantity": "1",
                "unit_price": "100000.00",
                "subtotal": "100000.00",
                "tax_rate": "19",
                "tax_amount": "19000.00",
                "tax_type": "01",
            }],
            subtotal=Decimal("100000.00"),
            tax_total=Decimal("19000.00"),
            total=Decimal("119000.00"),
        )
        defaults.update(kwargs)
        builder = DianInvoiceXmlBuilder(**defaults)
        return builder.build()

    def test_has_ubl_version_21(self):
        xml = self._build_sample_xml()
        assert "UBLVersionID" in xml
        assert ">2.1<" in xml

    def test_has_profile_execution_id(self):
        xml = self._build_sample_xml()
        assert "ProfileExecutionID" in xml
        assert ">2<" in xml

    def test_customization_id_10(self):
        xml = self._build_sample_xml()
        assert "CustomizationID" in xml
        assert ">10<" in xml

    def test_has_dian_extensions(self):
        xml = self._build_sample_xml()
        assert "DianExtensions" in xml

    def test_has_invoice_control(self):
        xml = self._build_sample_xml()
        assert "InvoiceControl" in xml
        assert "InvoiceAuthorization" in xml
        assert "AuthorizationPeriod" in xml
        assert "AuthorizedInvoices" in xml

    def test_has_software_provider(self):
        xml = self._build_sample_xml()
        assert "SoftwareProvider" in xml
        assert "ProviderID" in xml
        assert "SoftwareID" in xml

    def test_has_software_security_code(self):
        xml = self._build_sample_xml()
        assert "SoftwareSecurityCode" in xml

    def test_has_authorization_provider(self):
        xml = self._build_sample_xml()
        assert "AuthorizationProvider" in xml
        assert "800197268" in xml

    def test_has_qr_code(self):
        xml = self._build_sample_xml()
        assert "QRCode" in xml
        assert "catalogovpfe.dian.gov.co" in xml

    def test_has_uuid_element(self):
        xml = self._build_sample_xml()
        assert "UUID" in xml
        assert ">" + "A" * 96 + "<" in xml

    def test_invoice_type_code_numeric(self):
        xml = self._build_sample_xml()
        assert ">01<" in xml

    def test_endpoint_id_scheme(self):
        xml = self._build_sample_xml()
        assert 'schemeID="9"' in xml

    def test_supplier_party_has_scheme_name(self):
        xml = self._build_sample_xml()
        assert 'schemeName="31"' in xml

    def test_has_two_ubl_extensions(self):
        xml = self._build_sample_xml()
        import re
        assert len(re.findall(r'<ext:UBLExtension>', xml)) == 2


class TestConfigCompliance:
    """Tests de cumplimiento de configuración DIAN."""

    def test_environment_code_habilitacion(self):
        config = DIANConfig(environment="habilitacion")
        assert config.environment_code == "2"

    def test_environment_code_produccion(self):
        config = DIANConfig(environment="produccion")
        assert config.environment_code == "1"

    def test_soap_action_format(self):
        config = DIANConfig()
        action = config.get_soap_action("SendBillSync")
        assert action == "http://wcf.dian.colombia/IWcfDianCustomerServices/SendBillSync"

    def test_soap_url_habilitacion(self):
        config = DIANConfig(environment="habilitacion")
        url = config.get_soap_url()
        assert "vpfe-habilitacion.dian.gov.co" in url

    def test_soap_url_produccion(self):
        config = DIANConfig(environment="produccion")
        url = config.get_soap_url()
        assert "vpfe.dian.gov.co" in url
