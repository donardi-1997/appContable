from enum import Enum


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    SIGNED = "SIGNED"
    SENDING = "SENDING"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"
    PENDING = "PENDING"


class InvoiceEnvironment(str, Enum):
    HABILITACION = "habilitacion"
    PRODUCCION = "produccion"


class DocumentType(str, Enum):
    FACTURA_VENTA = "01"
    FACTURA_EXPORTACION = "02"
    DOCUMENTO_TRANSMISION = "03"
    FACTURA_TIPO_04 = "04"
    DOCUMENTO_SOPORTE = "05"
    POS = "20"
    NOTA_CREDITO = "91"
    NOTA_DEBITO = "92"


CUFE_DOCUMENTS = frozenset({
    DocumentType.FACTURA_VENTA,
    DocumentType.FACTURA_EXPORTACION,
    DocumentType.FACTURA_TIPO_04,
})

CUDE_DOCUMENTS = frozenset({
    DocumentType.POS,
    DocumentType.NOTA_CREDITO,
    DocumentType.NOTA_DEBITO,
    DocumentType.DOCUMENTO_SOPORTE,
})


class TaxType(str, Enum):
    IVA = "01"
    IC = "02"
    ICA = "03"
    INC = "04"
    RETE_IVA = "05"
    RETE_RENTA = "06"
    RETE_ICA = "07"
    IC_PORCENTUAL = "08"
    FTO_HORTICULTURA = "20"
    TIMBRE = "21"
    INC_BOLSAS = "22"
    IN_CARBONO = "23"
    NO_APLICA = "ZZ"


TAX_TYPE_NAMES = {
    TaxType.IVA: "IVA",
    TaxType.IC: "IC",
    TaxType.ICA: "ICA",
    TaxType.INC: "INC",
    TaxType.RETE_IVA: "ReteIVA",
    TaxType.RETE_RENTA: "ReteRenta",
    TaxType.RETE_ICA: "ReteICA",
    TaxType.IC_PORCENTUAL: "IC Porcentual",
    TaxType.FTO_HORTICULTURA: "Fondo Fomento Hortifruticola",
    TaxType.TIMBRE: "Impuesto de Timbre",
    TaxType.INC_BOLSAS: "INC Bolsas Plasticas",
    TaxType.IN_CARBONO: "Impuesto Nacional al Carbono",
    TaxType.NO_APLICA: "No Aplica",
}


CUFE_TAX_ORDER = (TaxType.IVA, TaxType.INC, TaxType.ICA)


class IdentificationType(str, Enum):
    REGISTRO_CIVIL = "11"
    TARJETA_IDENTIDAD = "12"
    CEDULA_CIUDADANIA = "13"
    TARJETA_EXTRANJERIA = "21"
    CEDULA_EXTRANJERIA = "22"
    NIT = "31"
    PASAPORTE = "41"
    DOCUMENTO_EXTRANJERO = "42"
    PEP = "47"
    PPT = "48"
    NIT_OTRO_PAIS = "50"
    NUIP = "91"


class PersonType(str, Enum):
    JURIDICA = "1"
    NATURAL = "2"


class FiscalResponsibility(str, Enum):
    GRAN_CONTRIBUYENTE = "O-13"
    AUTORRETENEDOR = "O-15"
    AGENTE_RETENCION_IVA = "O-23"
    REGIMEN_SIMPLE = "O-47"
    NO_APLICA = "R-99-PN"


class PaymentForm(str, Enum):
    CONTADO = "1"
    CREDITO = "2"


PAYMENT_FORM_NAMES = {
    PaymentForm.CONTADO: "Contado",
    PaymentForm.CREDITO: "Crédito",
}


class PaymentMethod(str, Enum):
    EFECTIVO = "10"
    CHEQUE = "20"
    TRANSFERENCIA_CREDITO = "30"
    CONSIGNACION_BANCARIA = "42"
    TRANSFERENCIA_DEBITO = "47"
    TARJETA_CREDITO = "48"
    TARJETA_DEBITO = "49"
    OTRO = "ZZZ"


class DIANStatusCode:
    ACCEPTED = "00"
    ACCEPTED_WITH_OBSERVATIONS = "01"
    REJECTED = "02"
    INVALID_SIGNATURE = "03"
    DOCUMENT_IN_PROCESS = "04"
    DUPLICATE_DOCUMENT = "06"
    INVALID_XML = "09"
    INVALID_CUFE = "10"
    CERTIFICATE_ERROR = "11"
    UNAUTHORIZED = "12"
    INTERNAL_ERROR = "13"

    HUMAN_READABLE = {
        "00": "Aceptado",
        "01": "Aceptado con observaciones",
        "02": "Rechazado",
        "03": "Firma inválida",
        "04": "Documento en proceso",
        "06": "Documento duplicado",
        "09": "XML inválido",
        "10": "CUFE inválido",
        "11": "Error en certificado",
        "12": "No autorizado",
        "13": "Error interno",
    }

    @classmethod
    def get_message(cls, code: str) -> str:
        return cls.HUMAN_READABLE.get(code, f"Código desconocido: {code}")
