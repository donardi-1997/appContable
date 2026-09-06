import json
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from ..invoice_provider import (
    ElectronicInvoiceProvider,
    InvoiceItemData,
    InvoiceResult,
    InvoiceStatusResult,
)
from .cufe import calculate_cufe, calculate_qr_url, calculate_software_security_code
from .config import DIANConfig
from .enums import (
    DocumentType,
    InvoiceStatus,
    TaxType,
    TAX_TYPE_NAMES,
    CUFE_TAX_ORDER,
)
from .errors import (
    DianConfigurationError,
    DianError,
    DianRejectedError,
    DianTransmissionError,
)
from .response_parser import parse_dian_response
from .signer import DianXmlSigner
from .soap_client import DianSoapClient
from .validators import validate_company_info, validate_invoice_data, validate_resolution, validate_tax_totals
from .xml_builder import DianInvoiceXmlBuilder


def _decimal_str(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


class DianElectronicInvoiceProvider(ElectronicInvoiceProvider):
    """Proveedor de facturación electrónica para la DIAN (Colombia).

    Implementa el flujo completo según el Anexo Técnico v1.9:
    1. Validación de configuración y datos
    2. Generación de XML UBL 2.1 con DianExtensions
    3. Cálculo de CUFE (SHA-384, 15 campos)
    4. Cálculo de SoftwareSecurityCode
    5. Generación de QR URL
    6. Firma XAdES-Lite
    7. Envío SOAP con WS-Security
    8. Parsing de respuesta DIAN
    """

    def __init__(self, config: DIANConfig | None = None):
        self._config = config or DIANConfig()
        self._soap_client = DianSoapClient()
        self._signer = DianXmlSigner()
        self._xml_cache: dict[str, dict[str, Any]] = {}

    @property
    def config(self) -> DIANConfig:
        return self._config

    def create_invoice(
        self,
        invoice_number: str,
        prefix: str,
        customer_name: str,
        customer_document_type: str | None,
        customer_document_number: str | None,
        customer_email: str | None,
        customer_address: str | None,
        customer_phone: str | None,
        items: list[InvoiceItemData],
        subtotal: Decimal,
        tax_total: Decimal,
        total: Decimal,
        environment: str = "sandbox",
    ) -> InvoiceResult:
        try:
            self._config.validate()
        except DianConfigurationError as e:
            return InvoiceResult(
                success=False,
                provider="dian",
                error_message=str(e),
            )

        items_dicts = []
        for item in items:
            items_dicts.append({
                "product_name": item.product_name,
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
                "subtotal": str(item.subtotal),
                "tax_rate": str(item.tax_rate),
                "tax_amount": str(item.tax_amount),
                "tax_type": item.tax_type,
            })

        item_validation_errors = []
        for idx, item_dict in enumerate(items_dicts):
            from .validators import validate_item
            errs = validate_item(item_dict, idx + 1)
            item_validation_errors.extend(errs)

        invoice_validation_errors = validate_invoice_data({
            "invoice_number": invoice_number,
            "prefix": prefix,
            "customer_name": customer_name,
            "items": items_dicts,
            "subtotal": subtotal,
            "tax_total": tax_total,
            "total": total,
        })

        all_validation_errors = item_validation_errors + invoice_validation_errors
        if all_validation_errors:
            return InvoiceResult(
                success=False,
                provider="dian",
                error_message="Errores de validación: " + "; ".join(all_validation_errors),
            )

        now = datetime.now(timezone.utc)
        invoice_date = now.strftime("%Y-%m-%d")
        invoice_time = now.strftime("%H:%M:%S-05:00")

        full_invoice_number = f"{prefix}{invoice_number}"

        provider_ref = f"DIAN-{full_invoice_number}-{secrets.token_hex(4).upper()}"

        full_number_for_cufe = f"{prefix}{invoice_number}"

        tax_totals: dict[str, Decimal] = {}
        for item in items:
            tax_code = item.tax_type
            if tax_code not in tax_totals:
                tax_totals[tax_code] = Decimal("0")
            tax_totals[tax_code] += item.tax_amount

        for tc in CUFE_TAX_ORDER:
            if tc.value not in tax_totals:
                tax_totals[tc.value] = Decimal("0")

        try:
            cufe = calculate_cufe(
                document_type=DocumentType.FACTURA_VENTA.value,
                invoice_number=full_number_for_cufe,
                issue_date=invoice_date,
                issue_time=invoice_time,
                line_extension_amount=subtotal,
                tax_totals=tax_totals,
                payable_amount=total,
                supplier_nit=self._config.nit,
                customer_id=customer_document_number or "2222222222222",
                technical_key=self._config.technical_key or self._config.software_pin,
                environment_code=self._config.environment_code,
            )
        except Exception as e:
            return InvoiceResult(
                success=False,
                provider="dian",
                error_message=f"Error al calcular el CUFE: {str(e)}",
            )

        software_security_code = calculate_software_security_code(
            software_id=self._config.software_id,
            pin=self._config.software_pin,
            document_number=full_number_for_cufe,
        )

        qr_url = calculate_qr_url(cufe)

        try:
            builder = DianInvoiceXmlBuilder(
                invoice_number=invoice_number,
                prefix=prefix,
                issue_date=invoice_date,
                issue_time=invoice_time,
                invoice_type_code=DocumentType.FACTURA_VENTA.value,
                customer_id_type=customer_document_type or "13",
                customer_id=customer_document_number or "2222222222222",
                customer_name=customer_name,
                customer_address=customer_address or "",
                customer_email=customer_email or "",
                supplier_name=self._config.nit,
                supplier_nit=self._config.nit,
                supplier_dv=self._config.dv,
                supplier_address="",
                supplier_municipality="",
                supplier_department="",
                supplier_country="CO",
                supplier_phone="",
                supplier_email="",
                supplier_regime="O-47",
                resolution_number=self._config.resolution_number,
                resolution_prefix=self._config.resolution_prefix,
                resolution_from=self._config.resolution_from,
                resolution_to=self._config.resolution_to,
                resolution_start_date=self._config.resolution_start_date,
                resolution_end_date=self._config.resolution_end_date,
                payment_form="1",
                payment_method="10",
                payment_due_date=invoice_date,
                items=items_dicts,
                subtotal=subtotal,
                tax_total=tax_total,
                total=total,
                environment_code=self._config.environment_code,
                software_id=self._config.software_id,
                software_provider_nit=self._config.software_provider_nit or self._config.nit,
                software_security_code=software_security_code,
                qr_url=qr_url,
                cufe=cufe,
            )
            unsigned_xml = builder.build_bytes()
        except Exception as e:
            return InvoiceResult(
                success=False,
                provider="dian",
                error_message=f"Error al generar el XML: {str(e)}",
            )

        try:
            signed_xml = self._signer.sign_xml(
                unsigned_xml,
                self._config.certificate_path,
                self._config.certificate_password,
            )
        except Exception as e:
            return InvoiceResult(
                success=False,
                provider="dian",
                provider_reference=provider_ref,
                error_message=f"Error al firmar el documento: {str(e)}",
            )

        self._xml_cache[provider_ref] = {
            "unsigned_xml": unsigned_xml,
            "signed_xml": signed_xml,
            "cufe": cufe,
            "invoice_number": full_number_for_cufe,
            "status": InvoiceStatus.SIGNED.value,
        }

        try:
            dian_response = self._soap_client.send_document(signed_xml, self._config)
        except DianTransmissionError as e:
            self._xml_cache[provider_ref]["status"] = InvoiceStatus.ERROR.value
            return InvoiceResult(
                success=False,
                provider="dian",
                provider_reference=provider_ref,
                cufe=cufe,
                error_message=str(e),
                dian_response={"error": str(e)},
            )
        except Exception as e:
            self._xml_cache[provider_ref]["status"] = InvoiceStatus.ERROR.value
            return InvoiceResult(
                success=False,
                provider="dian",
                provider_reference=provider_ref,
                cufe=cufe,
                error_message=f"Error inesperado al enviar a la DIAN: {str(e)}",
            )

        status_code = dian_response.get("status_code", "")
        status_msg = dian_response.get("status_message", "")
        errors = dian_response.get("errors", [])

        if status_code == "00" or status_code == "01":
            final_status = InvoiceStatus.ACCEPTED.value
            success = True
            error_msg = None
        elif status_code == "02":
            final_status = InvoiceStatus.REJECTED.value
            success = False
            error_msg = f"Factura rechazada: {status_msg}"
            if errors:
                error_msg += " Errores: " + "; ".join(errors)
        elif status_code == "04":
            final_status = InvoiceStatus.PENDING.value
            success = True
            error_msg = None
        else:
            final_status = InvoiceStatus.ERROR.value
            success = False
            error_msg = f"Estado DIAN {status_code}: {status_msg}"
            if errors:
                error_msg += " Errores: " + "; ".join(errors)

        self._xml_cache[provider_ref]["status"] = final_status
        self._xml_cache[provider_ref]["dian_response"] = dian_response

        return InvoiceResult(
            success=success,
            provider="dian",
            provider_reference=provider_ref,
            cufe=cufe,
            qr_data=qr_url,
            status=final_status,
            dian_response=dian_response,
            error_message=error_msg,
            issued_at=now,
        )

    def get_invoice_status(
        self,
        provider_reference: str,
    ) -> InvoiceStatusResult:
        cached = self._xml_cache.get(provider_reference)
        if not cached:
            return InvoiceStatusResult(
                status=InvoiceStatus.ERROR.value,
                provider_reference=provider_reference,
                error_message="Referencia no encontrada en caché",
            )

        try:
            self._config.validate()
            invoice_number = cached.get("invoice_number", "")
            response = self._soap_client.query_status(invoice_number, self._config)
            status_code = response.get("status_code", "")
            from .enums import DIANStatusCode
            status_msg = DIANStatusCode.get_message(status_code)

            cached["status"] = status_code
            cached["dian_response"] = response

            return InvoiceStatusResult(
                status=status_code,
                provider_reference=provider_reference,
                cufe=cached.get("cufe"),
                dian_response=response,
                error_message=None if status_code in ("00", "01", "04") else status_msg,
            )
        except DianConfigurationError as e:
            return InvoiceStatusResult(
                status=InvoiceStatus.ERROR.value,
                provider_reference=provider_reference,
                error_message=str(e),
            )
        except Exception as e:
            return InvoiceStatusResult(
                status=InvoiceStatus.ERROR.value,
                provider_reference=provider_reference,
                error_message=f"Error al consultar estado: {str(e)}",
            )

    def get_xml(
        self,
        provider_reference: str,
    ) -> str | None:
        cached = self._xml_cache.get(provider_reference)
        if not cached:
            return None
        signed = cached.get("signed_xml")
        if isinstance(signed, bytes):
            return signed.decode("utf-8")
        return signed

    def get_pdf_url(
        self,
        provider_reference: str,
    ) -> str | None:
        return None

    def get_cufe(
        self,
        provider_reference: str,
    ) -> str | None:
        cached = self._xml_cache.get(provider_reference)
        if not cached:
            return None
        return cached.get("cufe")
