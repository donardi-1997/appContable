class DianError(Exception):
    """Excepción base para errores del módulo DIAN."""

    def __init__(self, message: str = "Error desconocido en el módulo DIAN"):
        self.message = message
        super().__init__(self.message)


class DianConfigurationError(DianError):
    """Error de configuración del proveedor DIAN."""

    def __init__(self, message: str = "Error de configuración DIAN: faltan parámetros obligatorios"):
        self.message = message
        super().__init__(self.message)


class DianCertificateError(DianError):
    """Error al cargar o validar el certificado digital."""

    def __init__(self, message: str = "Error al cargar el certificado digital. Verifique la ruta y contraseña"):
        self.message = message
        super().__init__(self.message)


class DianXmlValidationError(DianError):
    """Error de validación del XML generado."""

    def __init__(self, message: str = "El XML generado no cumple con el formato UBL 2.1 requerido por la DIAN"):
        self.message = message
        super().__init__(self.message)


class DianSignatureError(DianError):
    """Error al firmar digitalmente el documento."""

    def __init__(self, message: str = "Error al firmar el documento XML digitalmente"):
        self.message = message
        super().__init__(self.message)


class DianTransmissionError(DianError):
    """Error al transmitir el documento a la DIAN."""

    def __init__(self, message: str = "Error al transmitir el documento a la DIAN. Intente nuevamente"):
        self.message = message
        super().__init__(self.message)


class DianRejectedError(DianError):
    """La DIAN rechazó el documento transmitido."""

    def __init__(self, message: str = "La DIAN rechazó el documento. Revise los datos y corrija los errores"):
        self.message = message
        super().__init__(self.message)
