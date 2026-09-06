import re
from typing import Any


def parse_dian_response(raw_response: str | None) -> dict[str, Any]:
    """
    Analiza la respuesta SOAP de la DIAN y extrae información estructurada.

    Retorna un diccionario con:
        - status_code: código de estado DIAN
        - status_message: mensaje legible del estado
        - errors: lista de errores encontrados
        - reference_id: identificador de referencia del documento
        - acceptance_date: fecha de aceptación si existe
        - raw_response: respuesta completa sin parsear
    """
    result: dict[str, Any] = {
        "status_code": "",
        "status_message": "",
        "errors": [],
        "reference_id": "",
        "acceptance_date": "",
        "raw_response": raw_response or "",
    }

    if not raw_response or not raw_response.strip():
        result["status_code"] = "ERROR"
        result["status_message"] = "No se recibió respuesta de la DIAN"
        result["errors"].append("Respuesta vacía del servicio web")
        return result

    status_code_match = re.search(
        r"<StatusCode[^>]*>([^<]+)</StatusCode>", raw_response
    )
    if status_code_match:
        result["status_code"] = status_code_match.group(1).strip()
        from .enums import DIANStatusCode
        result["status_message"] = DIANStatusCode.get_message(result["status_code"])

    status_text_match = re.search(
        r"<StatusMessage[^>]*>([^<]+)</StatusMessage>", raw_response
    )
    if status_text_match:
        result["status_message"] = status_text_match.group(1).strip()

    reference_match = re.search(
        r"<ReferenceID[^>]*>([^<]+)</ReferenceID>", raw_response
    )
    if reference_match:
        result["reference_id"] = reference_match.group(1).strip()

    acceptance_match = re.search(
        r"<AcceptanceDate[^>]*>([^<]+)</AcceptanceDate>", raw_response
    )
    if acceptance_match:
        result["acceptance_date"] = acceptance_match.group(1).strip()

    error_matches = re.findall(
        r"<ErrorMessage[^>]*>([^<]+)</ErrorMessage>", raw_response
    )
    if error_matches:
        result["errors"].extend([e.strip() for e in error_matches])

    warning_matches = re.findall(
        r"<WarningMessage[^>]*>([^<]+)</WarningMessage>", raw_response
    )
    if warning_matches:
        result["errors"].extend([f"Aviso: {w.strip()}" for w in warning_matches])

    body_match = re.search(
        r"<soap:Body[^>]*>(.*?)</soap:Body>",
        raw_response,
        re.DOTALL,
    )
    if body_match:
        body_text = body_match.group(1)
        fault_match = re.search(r"<soap:Fault>(.*?)</soap:Fault>", body_text, re.DOTALL)
        if fault_match:
            fault_text = fault_match.group(1)
            faultstring_match = re.search(r"<faultstring>([^<]+)</faultstring>", fault_text)
            if faultstring_match:
                result["status_code"] = "SOAP_FAULT"
                result["status_message"] = faultstring_match.group(1).strip()
                result["errors"].append(
                    f"Error SOAP: {faultstring_match.group(1).strip()}"
                )

    envelope_match = re.search(
        r"<GetStatusZipResponse[^>]*>(.*?)</GetStatusZipResponse>",
        raw_response,
        re.DOTALL,
    )
    if envelope_match:
        resp_body = envelope_match.group(1)
        if not result["status_code"]:
            sc_match = re.search(r"<StatusCode[^>]*>([^<]+)</StatusCode>", resp_body)
            if sc_match:
                result["status_code"] = sc_match.group(1).strip()
                from .enums import DIANStatusCode
                result["status_message"] = DIANStatusCode.get_message(result["status_code"])

    if not result["status_code"]:
        result["status_code"] = "UNKNOWN"
        result["status_message"] = "No se pudo determinar el estado de la respuesta"

    return result
