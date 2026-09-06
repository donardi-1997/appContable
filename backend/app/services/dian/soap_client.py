import base64
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding

from .config import DIANConfig
from .errors import DianTransmissionError

SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
WCF_NS = "http://wcf.dian.colombia"
WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
WSA_NS = "http://www.w3.org/2005/08/addressing"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"


class DianSoapClient:
    """Cliente SOAP para comunicación con los servicios web de la DIAN.

    Implementa SOAP 1.2 con WS-Security (BinarySecurityToken + Timestamp + Signature)
    y WS-Addressing según la Guía Herramienta para el Consumo de Web Services de la DIAN.
    """

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/xml",
        })

    def send_document(self, xml_bytes: bytes, config: DIANConfig) -> dict[str, Any]:
        content_b64 = base64.b64encode(xml_bytes).decode("utf-8")
        file_name = f"FE_{config.nit}_{int(time.time())}.xml"

        if config.environment == "produccion":
            soap_action = config.get_soap_action("SendBillSync")
            method_name = "SendBillSync"
        else:
            soap_action = config.get_soap_action("SetTrialInvoice")
            method_name = "SetTrialInvoice"

        envelope = self._build_soap_envelope(
            method_name=method_name,
            file_name=file_name,
            content=content_b64,
            soap_action=soap_action,
            to_url=config.get_soap_url(),
            config=config,
        )

        return self._send_with_retry(
            envelope=envelope,
            soap_url=config.get_soap_url(),
            soap_action=soap_action,
            config=config,
            max_retries=3,
        )

    def query_status(self, track_id: str, config: DIANConfig) -> dict[str, Any]:
        soap_action = config.get_soap_action("GetStatus")

        envelope = self._build_get_status_envelope(
            track_id=track_id,
            soap_action=soap_action,
            to_url=config.get_soap_url(),
            config=config,
        )

        return self._send_with_retry(
            envelope=envelope,
            soap_url=config.get_soap_url(),
            soap_action=soap_action,
            config=config,
            max_retries=3,
        )

    def _build_soap_envelope(
        self,
        *,
        method_name: str,
        file_name: str,
        content: str,
        soap_action: str,
        to_url: str,
        config: DIANConfig,
    ) -> str:
        timestamp_id = f"TS-{uuid.uuid4().hex.upper()}"
        token_id = f"X509-{uuid.uuid4().hex.upper()}"
        to_id = f"id-{uuid.uuid4().hex.upper()}"

        now = datetime.now(timezone.utc)
        created = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        expires = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        binary_token = ""
        if config.certificate_path:
            try:
                binary_token = self._load_certificate_b64(
                    config.certificate_path, config.certificate_password
                )
            except Exception:
                pass

        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="{SOAP_NS}"
               xmlns:wcf="{WCF_NS}">
  <soap:Header xmlns:wsa="{WSA_NS}">
    <wsse:Security xmlns:wsse="{WSSE_NS}" xmlns:wsu="{WSU_NS}">
      <wsu:Timestamp wsu:Id="{timestamp_id}">
        <wsu:Created>{created}</wsu:Created>
        <wsu:Expires>{expires}</wsu:Expires>
      </wsu:Timestamp>
      <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"
        ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0"
        wsu:Id="{token_id}">{binary_token}</wsse:BinarySecurityToken>
    </wsse:Security>
    <wsa:Action>{soap_action}</wsa:Action>
    <wsa:To wsu:Id="{to_id}" xmlns:wsu="{WSU_NS}">{to_url}</wsa:To>
  </soap:Header>
  <soap:Body>
    <wcf:{method_name}>
      <wcf:fileName>{file_name}</wcf:fileName>
      <wcf:content>{content}</wcf:content>
      <wcf:ramlAttachment></wcf:ramlAttachment>
    </wcf:{method_name}>
  </soap:Body>
</soap:Envelope>"""

        return envelope

    def _build_get_status_envelope(
        self,
        *,
        track_id: str,
        soap_action: str,
        to_url: str,
        config: DIANConfig,
    ) -> str:
        timestamp_id = f"TS-{uuid.uuid4().hex.upper()}"
        token_id = f"X509-{uuid.uuid4().hex.upper()}"
        to_id = f"id-{uuid.uuid4().hex.upper()}"

        now = datetime.now(timezone.utc)
        created = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        expires = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        binary_token = ""
        if config.certificate_path:
            try:
                binary_token = self._load_certificate_b64(
                    config.certificate_path, config.certificate_password
                )
            except Exception:
                pass

        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="{SOAP_NS}"
               xmlns:wcf="{WCF_NS}">
  <soap:Header xmlns:wsa="{WSA_NS}">
    <wsse:Security xmlns:wsse="{WSSE_NS}" xmlns:wsu="{WSU_NS}">
      <wsu:Timestamp wsu:Id="{timestamp_id}">
        <wsu:Created>{created}</wsu:Created>
        <wsu:Expires>{expires}</wsu:Expires>
      </wsu:Timestamp>
      <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"
        ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0"
        wsu:Id="{token_id}">{binary_token}</wsse:BinarySecurityToken>
    </wsse:Security>
    <wsa:Action>{soap_action}</wsa:Action>
    <wsa:To wsu:Id="{to_id}" xmlns:wsu="{WSU_NS}">{to_url}</wsa:To>
  </soap:Header>
  <soap:Body>
    <wcf:GetStatus>
      <wcf:trackId>{track_id}</wcf:trackId>
    </wcf:GetStatus>
  </soap:Body>
</soap:Envelope>"""

        return envelope

    def _load_certificate_b64(self, certificate_path: str, certificate_password: str) -> str:
        with open(certificate_path, "rb") as f:
            pfx_data = f.read()
        password_bytes = certificate_password.encode("utf-8") if certificate_password else None
        private_key, certificate, chain = pkcs12.load_key_and_certificates(
            pfx_data, password_bytes
        )
        if certificate is None:
            return ""
        cert_der = certificate.public_bytes(Encoding.DER)
        return base64.b64encode(cert_der).decode("utf-8")

    def _send_with_retry(
        self,
        envelope: str,
        soap_url: str,
        soap_action: str,
        config: DIANConfig,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self._session.post(
                    soap_url,
                    data=envelope.encode("utf-8"),
                    headers={
                        "Content-Type": "application/soap+xml; charset=utf-8",
                        "SOAPAction": soap_action,
                    },
                    timeout=60,
                )

                if response.status_code == 500:
                    raise DianTransmissionError(
                        f"La DIAN retornó un error HTTP 500 "
                        f"(intento {attempt}/{max_retries})"
                    )

                if response.status_code != 200:
                    raise DianTransmissionError(
                        f"Error HTTP {response.status_code} al comunicarse con la DIAN "
                        f"(intento {attempt}/{max_retries})"
                    )

                return self._parse_soap_response(response.text)

            except DianTransmissionError:
                raise
            except requests.Timeout:
                last_error = DianTransmissionError(
                    f"Tiempo de espera agotado al comunicarse con la DIAN "
                    f"(intento {attempt}/{max_retries})"
                )
            except requests.ConnectionError:
                last_error = DianTransmissionError(
                    f"Error de conexión con la DIAN "
                    f"(intento {attempt}/{max_retries})"
                )
            except Exception as e:
                last_error = DianTransmissionError(
                    f"Error inesperado al comunicarse con la DIAN: {str(e)} "
                    f"(intento {attempt}/{max_retries})"
                )

            if attempt < max_retries:
                backoff = attempt * 2
                time.sleep(backoff)

        if last_error:
            raise last_error
        return {}

    def _parse_soap_response(self, raw_response: str) -> dict[str, Any]:
        from .response_parser import parse_dian_response
        return parse_dian_response(raw_response)
