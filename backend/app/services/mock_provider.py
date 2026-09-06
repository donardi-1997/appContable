import hashlib
import secrets
from datetime import datetime
from decimal import Decimal

from .invoice_provider import (
    ElectronicInvoiceProvider,
    InvoiceItemData,
    InvoiceResult,
    InvoiceStatusResult,
)


class MockElectronicInvoiceProvider(ElectronicInvoiceProvider):
    """Proveedor mock para desarrollo y pruebas.

    NO genera facturas válidas ante DIAN.
    Simula el flujo completo en ambiente de sandbox.
    Todas las facturas generadas aquí son EXCLUSIVAMENTE
    para pruebas internas.
    """

    def _generate_cufe(
        self,
        invoice_number: str,
        prefix: str,
        total: Decimal,
    ) -> str:
        raw = (
            f"{prefix}{invoice_number}"
            f"{total}"
            f"{secrets.token_hex(8)}"
        )
        return hashlib.sha256(
            raw.encode()
        ).hexdigest().upper()

    def _generate_reference(self) -> str:
        return f"MOCK-{secrets.token_hex(6).upper()}"

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
        if environment != "sandbox":
            return InvoiceResult(
                success=False,
                provider="mock",
                error_message=(
                    "El proveedor mock solo funciona "
                    "en ambiente sandbox"
                ),
            )

        provider_ref = self._generate_reference()
        cufe = self._generate_cufe(
            invoice_number, prefix, total
        )

        items_data = []
        for item in items:
            items_data.append({
                "product": item.product_name,
                "qty": str(item.quantity),
                "unit_price": str(item.unit_price),
                "subtotal": str(item.subtotal),
                "tax_rate": str(item.tax_rate),
                "tax_amount": str(item.tax_amount),
                "tax_type": item.tax_type,
            })

        qr_payload = (
            f"NIT-emisor|{invoice_number}"
            f"|{cufe[:10]}|{total}"
        )

        now = datetime.utcnow()

        return InvoiceResult(
            success=True,
            provider="mock",
            provider_reference=provider_ref,
            cufe=cufe,
            qr_data=qr_payload,
            status="ACCEPTED",
            dian_response={
                "environment": "sandbox",
                "message": (
                    "Factura simulada exitosamente. "
                    "ESTE DOCUMENTO NO TIENE VALIDEZ "
                    "FRENTE A LA DIAN."
                ),
                "provider": "mock",
                "timestamp": now.isoformat(),
                "invoice_number": invoice_number,
                "prefix": prefix,
                "subtotal": str(subtotal),
                "tax_total": str(tax_total),
                "total": str(total),
                "customer": customer_name,
                "items_count": len(items),
            },
            issued_at=now,
        )

    def get_invoice_status(
        self,
        provider_reference: str,
    ) -> InvoiceStatusResult:
        return InvoiceStatusResult(
            status="ACCEPTED",
            provider_reference=provider_reference,
            dian_response={
                "environment": "sandbox",
                "message": "Estado simulado",
            },
        )

    def get_xml(
        self,
        provider_reference: str,
    ) -> str | None:
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f"<factura>"
            f"<referencia>{provider_reference}</referencia>"
            f"<estado>ACCEPTED</estado>"
            f"<ambiente>sandbox</ambiente>"
            f"<nota>Documento simulado sin validez DIAN</nota>"
            f"</factura>"
        )

    def get_pdf_url(
        self,
        provider_reference: str,
    ) -> str | None:
        return None

    def get_cufe(
        self,
        provider_reference: str,
    ) -> str | None:
        return None
