from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class InvoiceItemData:
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    tax_type: str = "IVA"


@dataclass
class InvoiceResult:
    success: bool
    provider: str
    provider_reference: str | None = None
    cufe: str | None = None
    qr_data: str | None = None
    xml_url: str | None = None
    pdf_url: str | None = None
    status: str = "PENDING"
    dian_response: dict | None = None
    error_message: str | None = None
    issued_at: datetime | None = None


@dataclass
class InvoiceStatusResult:
    status: str
    provider_reference: str | None = None
    cufe: str | None = None
    dian_response: dict | None = None
    error_message: str | None = None


class ElectronicInvoiceProvider(ABC):
    """Interface abstracta para proveedores de facturación electrónica.

    Cada proveedor concreto (DIAN, mock, etc.) debe implementar
    estos métodos. La lógica de negocio NUNCA debe depender
    directamente de un proveedor específico.
    """

    @abstractmethod
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
        """Crear y enviar una factura electrónica."""
        ...

    @abstractmethod
    def get_invoice_status(
        self,
        provider_reference: str,
    ) -> InvoiceStatusResult:
        """Consultar el estado de una factura ante el proveedor."""
        ...

    @abstractmethod
    def get_xml(
        self,
        provider_reference: str,
    ) -> str | None:
        """Obtener el XML de la factura."""
        ...

    @abstractmethod
    def get_pdf_url(
        self,
        provider_reference: str,
    ) -> str | None:
        """Obtener la URL del PDF representación gráfica."""
        ...

    @abstractmethod
    def get_cufe(
        self,
        provider_reference: str,
    ) -> str | None:
        """Obtener el CUFE de una factura aceptada."""
        ...
