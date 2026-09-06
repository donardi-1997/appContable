import hashlib
from decimal import Decimal, ROUND_DOWN

from .enums import CUDE_DOCUMENTS, CUFE_DOCUMENTS, DocumentType, TaxType, CUFE_TAX_ORDER


def _truncate(value: Decimal, places: int = 2) -> str:
    """Trunca (no redondea) un Decimal a los decimales indicados."""
    quantizer = Decimal(10) ** -places
    return str(value.quantize(quantizer, rounding=ROUND_DOWN))


def _extract_tax_amount(
    tax_totals: dict[str, Decimal], tax_code: str
) -> Decimal:
    """Extrae el monto total de un impuesto específico del diccionario de totales."""
    return tax_totals.get(tax_code, Decimal("0"))


def calculate_cufe(
    *,
    document_type: str,
    invoice_number: str,
    issue_date: str,
    issue_time: str,
    line_extension_amount: Decimal,
    tax_totals: dict[str, Decimal],
    payable_amount: Decimal,
    supplier_nit: str,
    customer_id: str,
    technical_key: str,
    environment_code: str,
) -> str:
    """
    Calcula el CUFE o CUDE según la especificación DIAN Anexo Técnico v1.9.

    Fórmula oficial (15 campos concatenados):
        NumFac + FecFac + HorFac + ValFac
        + CodImp1 + ValImp1 (IVA)
        + CodImp2 + ValImp2 (INC)
        + CodImp3 + ValImp3 (ICA)
        + ValTot + NitOFE + NumAdq
        + ClTec/PIN + TipoAmb

    SHA-384 de la concatenación → 96 caracteres hexadecimales.

    Args:
        document_type: Código del tipo de documento ("01"=FE, "91"=NC, etc.)
        invoice_number: Número completo con prefijo (ej: "FE00000001")
        issue_date: Fecha de emisión YYYY-MM-DD
        issue_time: Hora de emisión HH:MM:SS-05:00
        line_extension_amount: Base gravable total (LineExtensionAmount)
        tax_totals: Diccionario {código_impuesto: monto_total}
            Ej: {"01": Decimal("190"), "04": Decimal("0"), "03": Decimal("0")}
        payable_amount: Total a pagar (PayableAmount)
        supplier_nit: NIT del emisor (sin dígito de verificación)
        customer_id: Número de documento del adquirente
        technical_key: Clave técnica (CUFE) o PIN del software (CUDE)
        environment_code: "1" = producción, "2" = habilitación

    Returns:
        CUFE/CUDE como cadena hexadecimal de 96 caracteres en mayúsculas
    """
    doc_type = DocumentType(document_type)

    if doc_type in CUFE_DOCUMENTS:
        secret_key = technical_key
    elif doc_type in CUDE_DOCUMENTS:
        secret_key = technical_key
    else:
        secret_key = technical_key

    tax_codes = CUFE_TAX_ORDER
    val_fac = _truncate(line_extension_amount)
    val_tot = _truncate(payable_amount)
    nit_ofe = supplier_nit.strip()

    parts = [
        invoice_number,
        issue_date,
        issue_time,
        val_fac,
    ]

    for tax_code in tax_codes:
        parts.append(tax_code.value)
        parts.append(_truncate(_extract_tax_amount(tax_totals, tax_code.value)))

    parts.extend([
        val_tot,
        nit_ofe,
        customer_id,
        secret_key,
        environment_code,
    ])

    concatenated = "".join(parts)
    return hashlib.sha384(concatenated.encode("utf-8")).hexdigest().upper()


def calculate_software_security_code(
    software_id: str,
    pin: str,
    document_number: str,
) -> str:
    """
    Calcula el SoftwareSecurityCode requerido en DianExtensions.

    Fórmula: SHA384(SoftwareID + PIN + NumFac)

    Args:
        software_id: UUID del software registrado en DIAN
        pin: PIN secreto del software
        document_number: Número completo del documento con prefijo

    Returns:
        Código de seguridad como hexadecimal de 96 caracteres en mayúsculas
    """
    raw = software_id + pin + document_number
    return hashlib.sha384(raw.encode("utf-8")).hexdigest().upper()


def calculate_qr_url(cufe: str) -> str:
    """
    Genera la URL para el código QR de la factura electrónica.

    Formato oficial: https://catalogovpfe.dian.gov.co/document/searchqr?documentkey={CUFE}

    Args:
        cufe: CUFE de 96 caracteres

    Returns:
        URL completa para el código QR
    """
    return f"https://catalogovpfe.dian.gov.co/document/searchqr?documentkey={cufe}"
