import os
from dataclasses import dataclass, field

from .errors import DianConfigurationError


@dataclass
class DIANConfig:
    """Configuración del proveedor DIAN cargada desde variables de entorno."""

    provider: str = field(
        default_factory=lambda: os.environ.get("ELECTRONIC_INVOICE_PROVIDER", "mock")
    )
    environment: str = field(
        default_factory=lambda: os.environ.get("DIAN_ENVIRONMENT", "habilitacion")
    )

    software_id: str = field(
        default_factory=lambda: os.environ.get("DIAN_SOFTWARE_ID", "")
    )
    software_pin: str = field(
        default_factory=lambda: os.environ.get("DIAN_SOFTWARE_PIN", "")
    )
    software_provider_nit: str = field(
        default_factory=lambda: os.environ.get("DIAN_SOFTWARE_PROVIDER_NIT", "")
    )
    test_set_id: str = field(
        default_factory=lambda: os.environ.get("DIAN_TEST_SET_ID", "")
    )

    certificate_path: str = field(
        default_factory=lambda: os.environ.get("DIAN_CERTIFICATE_PATH", "")
    )
    certificate_password: str = field(
        default_factory=lambda: os.environ.get("DIAN_CERTIFICATE_PASSWORD", "")
    )

    nit: str = field(
        default_factory=lambda: os.environ.get("DIAN_NIT", "")
    )
    dv: str = field(
        default_factory=lambda: os.environ.get("DIAN_DV", "")
    )

    resolution_number: str = field(
        default_factory=lambda: os.environ.get("DIAN_RESOLUTION_NUMBER", "")
    )
    resolution_prefix: str = field(
        default_factory=lambda: os.environ.get("DIAN_RESOLUTION_PREFIX", "FE")
    )
    resolution_from: str = field(
        default_factory=lambda: os.environ.get("DIAN_RESOLUTION_FROM", "")
    )
    resolution_to: str = field(
        default_factory=lambda: os.environ.get("DIAN_RESOLUTION_TO", "")
    )
    resolution_start_date: str = field(
        default_factory=lambda: os.environ.get("DIAN_RESOLUTION_START_DATE", "")
    )
    resolution_end_date: str = field(
        default_factory=lambda: os.environ.get("DIAN_RESOLUTION_END_DATE", "")
    )
    technical_key: str = field(
        default_factory=lambda: os.environ.get("DIAN_TECHNICAL_KEY", "")
    )

    habilitacion_soap_url: str = field(
        default_factory=lambda: os.environ.get(
            "DIAN_HABILITACION_URL",
            "https://vpfe-habilitacion.dian.gov.co/WcfDianCustomerServices.svc",
        )
    )
    produccion_soap_url: str = field(
        default_factory=lambda: os.environ.get(
            "DIAN_PRODUCCION_URL",
            "https://vpfe.dian.gov.co/WcfDianCustomerServices.svc",
        )
    )

    @property
    def environment_code(self) -> str:
        """Código de ambiente para CUFE y XML: '1' = producción, '2' = habilitación."""
        return "1" if self.environment == "produccion" else "2"

    def get_soap_url(self) -> str:
        if self.environment == "produccion":
            return self.produccion_soap_url
        return self.habilitacion_soap_url

    def get_soap_action(self, method: str) -> str:
        """Retorna el SOAPAction URI completo para el método dado."""
        return f"http://wcf.dian.colombia/IWcfDianCustomerServices/{method}"

    def validate(self) -> None:
        errors: list[str] = []

        if self.provider != "dian":
            return

        if not self.software_id:
            errors.append("DIAN_SOFTWARE_ID no está configurado")
        if not self.software_pin:
            errors.append("DIAN_SOFTWARE_PIN no está configurado")
        if not self.software_provider_nit:
            errors.append("DIAN_SOFTWARE_PROVIDER_NIT no está configurado")
        if not self.certificate_path:
            errors.append("DIAN_CERTIFICATE_PATH no está configurado")
        if not self.certificate_password:
            errors.append("DIAN_CERTIFICATE_PASSWORD no está configurado")
        if not self.nit:
            errors.append("DIAN_NIT no está configurado")
        if not self.resolution_number:
            errors.append("DIAN_RESOLUTION_NUMBER no está configurado")
        if not self.resolution_from:
            errors.append("DIAN_RESOLUTION_FROM no está configurado")
        if not self.resolution_to:
            errors.append("DIAN_RESOLUTION_TO no está configurado")
        if not self.resolution_start_date:
            errors.append("DIAN_RESOLUTION_START_DATE no está configurado")
        if not self.resolution_end_date:
            errors.append("DIAN_RESOLUTION_END_DATE no está configurado")

        if self.environment == "habilitacion" and not self.test_set_id:
            errors.append("DIAN_TEST_SET_ID es requerido en ambiente de habilitación")

        if errors:
            raise DianConfigurationError(
                "Configuración DIAN incompleta: " + "; ".join(errors)
            )
