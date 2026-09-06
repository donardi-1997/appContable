import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, NoEncryption, PrivateFormat
from cryptography.x509 import load_pem_x509_certificate
from cryptography.x509.oid import NameOID
import base64

from .errors import DianCertificateError, DianSignatureError

DS_NS = "http://www.w3.org/2000/09/xmldsig#"
UBL_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
EXT_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
XADES_NS = "http://uri.etsi.org/01903/v1.3.2#"
XADES141_NS = "http://uri.etsi.org/01903/v1.4.1#"

ET.register_namespace("ds", DS_NS)
ET.register_namespace("", UBL_NS)
ET.register_namespace("ext", EXT_NS)
ET.register_namespace("xades", XADES_NS)
ET.register_namespace("xades141", XADES141_NS)


class DianXmlSigner:
    """Firmante XML XAdES-Lite para documentos DIAN.

    Coloca la firma dentro del segundo ext:UBLExtension > ext:ExtensionContent
    según lo requerido por el Anexo Técnico de la DIAN.
    """

    def __init__(self):
        self._private_key = None
        self._certificate = None

    def load_pkcs12(self, certificate_path: str, certificate_password: str) -> None:
        try:
            with open(certificate_path, "rb") as f:
                pfx_data = f.read()
            password_bytes = certificate_password.encode("utf-8") if certificate_password else None
            private_key, certificate, chain = pkcs12.load_key_and_certificates(
                pfx_data, password_bytes
            )
            self._private_key = private_key
            self._certificate = certificate
        except FileNotFoundError:
            raise DianCertificateError(
                f"El archivo de certificado no fue encontrado en: {certificate_path}"
            )
        except Exception as e:
            raise DianCertificateError(
                f"Error al cargar el certificado PKCS12: {str(e)}"
            )

    def validate_certificate(self) -> bool:
        if self._certificate is None:
            raise DianCertificateError("No hay certificado cargado")
        now = datetime.now(timezone.utc)
        if self._certificate.not_valid_after_utc < now:
            raise DianCertificateError(
                "El certificado digital ha expirado. Renueve su certificado ante la DIAN"
            )
        return True

    def sign_xml(self, xml_bytes: bytes, certificate_path: str, certificate_password: str) -> bytes:
        self.load_pkcs12(certificate_path, certificate_password)
        self.validate_certificate()

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            raise DianSignatureError(f"Error al parsear el XML para firmar: {str(e)}")

        signature_id = f"xmldsig-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        key_info_id = f"xmldsig-{signature_id}-keyinfo"
        qualifier_id = f"qualifier-{signature_id}"
        signed_properties_id = f"-signedprops-{signature_id}"
        reference_uri = ""

        signed_info_canonical, signature_value, x509_data_b64 = self._compute_signature(
            root, reference_uri, signature_id, key_info_id
        )

        sig_element = ET.Element(f"{{{DS_NS}}}Signature")
        sig_element.set("Id", signature_id)
        sig_element.set("xmlns:ds", DS_NS)

        signed_info_el = self._build_signed_info(
            reference_uri, signature_id, key_info_id, signed_info_canonical
        )
        sig_element.append(signed_info_el)

        sig_value_el = ET.SubElement(sig_element, f"{{{DS_NS}}}SignatureValue")
        sig_value_el.text = base64.b64encode(signature_value).decode("utf-8")

        key_info_el = ET.SubElement(sig_element, f"{{{DS_NS}}}KeyInfo")
        key_info_el.set("Id", key_info_id)
        x509_data_el = ET.SubElement(key_info_el, f"{{{DS_NS}}}X509Data")
        x509_cert_el = ET.SubElement(x509_data_el, f"{{{DS_NS}}}X509Certificate")
        x509_cert_el.text = x509_data_b64

        self._add_xades_object(sig_element, signature_id, signed_properties_id)

        self._place_signature_in_ubl_extensions(root, sig_element)

        return ET.tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")

    def _compute_signature(
        self,
        root: ET.Element,
        reference_uri: str,
        signature_id: str,
        key_info_id: str,
    ) -> tuple[str, bytes, str]:
        canonical_xml = self._canonicalize(root)
        canonical_bytes = canonical_xml.encode("utf-8")

        digest_value = self._compute_digest(canonical_bytes)

        signed_info_canonical = self._build_signed_info_canonical(
            reference_uri, signature_id, key_info_id, digest_value
        )
        signed_info_bytes = signed_info_canonical.encode("utf-8")

        signature_value = self._private_key.sign(
            signed_info_bytes,
            padding=None,
            algorithm=hashes.SHA384(),
        )

        x509_der = self._certificate.public_bytes(Encoding.DER)
        x509_b64 = base64.b64encode(x509_der).decode("utf-8")

        return signed_info_canonical, signature_value, x509_b64

    def _compute_digest(self, data: bytes) -> str:
        digest = hashes.Hash(hashes.SHA384())
        digest.update(data)
        return base64.b64encode(digest.finalize()).decode("utf-8")

    def _canonicalize(self, element: ET.Element) -> str:
        xml_str = ET.tostring(element, encoding="unicode")
        lines = xml_str.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned.append(stripped)
        return "".join(cleaned)

    def _build_signed_info(
        self,
        reference_uri: str,
        signature_id: str,
        key_info_id: str,
        signed_info_canonical: str,
    ) -> ET.Element:
        signed_info_el = ET.Element(f"{{{DS_NS}}}SignedInfo")
        signed_info_el.set("xmlns:ds", DS_NS)

        ET.SubElement(signed_info_el, f"{{{DS_NS}}}CanonicalizationMethod").set(
            "Algorithm", "http://www.w3.org/2001/10/xml-exc-c14n#"
        )
        ET.SubElement(signed_info_el, f"{{{DS_NS}}}SignatureMethod").set(
            "Algorithm", "http://www.w3.org/2001/04/xmldsig-more#rsa-sha384"
        )

        reference = ET.SubElement(signed_info_el, f"{{{DS_NS}}}Reference")
        reference.set("URI", reference_uri)

        transforms = ET.SubElement(reference, f"{{{DS_NS}}}Transforms")
        ET.SubElement(transforms, f"{{{DS_NS}}}Transform").set(
            "Algorithm", "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
        )
        ET.SubElement(transforms, f"{{{DS_NS}}}Transform").set(
            "Algorithm", "http://www.w3.org/2001/10/xml-exc-c14n#"
        )

        ET.SubElement(reference, f"{{{DS_NS}}}DigestMethod").set(
            "Algorithm", "http://www.w3.org/2001/04/xmlenc#sha384"
        )
        ET.SubElement(reference, f"{{{DS_NS}}}DigestValue")

        return signed_info_el

    def _build_signed_info_canonical(
        self,
        reference_uri: str,
        signature_id: str,
        key_info_id: str,
        digest_value: str,
    ) -> str:
        signed_info_parts = [
            f'<ds:SignedInfo xmlns:ds="{DS_NS}">',
            f'  <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>',
            f'  <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha384"/>',
            f'  <ds:Reference URI="{reference_uri}">',
            f'    <ds:Transforms>',
            f'      <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>',
            f'      <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>',
            f"    </ds:Transforms>",
            f'    <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha384"/>',
            f"    <ds:DigestValue>{digest_value}</ds:DigestValue>",
            f"  </ds:Reference>",
            f"</ds:SignedInfo>",
        ]
        return "\n".join(signed_info_parts)

    def _add_xades_object(
        self,
        sig_element: ET.Element,
        signature_id: str,
        signed_properties_id: str,
    ) -> None:
        xades_obj = ET.SubElement(sig_element, f"{{{XADES_NS}}}Object")
        xades_obj.set("Id", f"xades-{signature_id}")

        signed_props = ET.SubElement(xades_obj, f"{{{XADES_NS}}}SignedProperties")
        signed_props.set("Id", signed_properties_id)

        sig_props = ET.SubElement(signed_props, f"{{{XADES_NS}}}SignedSignatureProperties")
        sig_time = ET.SubElement(sig_props, f"{{{XADES_NS}}}SigningTime")
        sig_time.set("Format", "xsd:dateTime")
        now = datetime.now(timezone.utc)
        sig_time.text = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        signing_cert = ET.SubElement(sig_props, f"{{{XADES_NS}}}SigningCertificate")
        cert_digest = ET.SubElement(signing_cert, f"{{{XADES_NS}}}CertDigest")

        if self._certificate:
            cert_der = self._certificate.public_bytes(Encoding.DER)
            digest = hashes.Hash(hashes.SHA384())
            digest.update(cert_der)
            digest_value = base64.b64encode(digest.finalize()).decode("utf-8")

            digest_method = ET.SubElement(cert_digest, f"{{{DS_NS}}}DigestMethod")
            digest_method.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha384")
            digest_val = ET.SubElement(cert_digest, f"{{{DS_NS}}}DigestValue")
            digest_val.text = digest_value

            issuer_serial = ET.SubElement(signing_cert, f"{{{XADES_NS}}}IssuerSerialV2")
            x509_issuer = ET.SubElement(issuer_serial, f"{{{DS_NS}}}X509IssuerName")
            if self._certificate.issuer:
                x509_issuer.text = ", ".join(
                    f"{attr.oid._name}={attr.value}"
                    for attr in self._certificate.issuer
                )
            x509_serial = ET.SubElement(issuer_serial, f"{{{DS_NS}}}X509SerialNumber")
            x509_serial.text = str(self._certificate.serial_number)

    def _place_signature_in_ubl_extensions(
        self, root: ET.Element, sig_element: ET.Element
    ) -> None:
        ext_ns_prefix = EXT_NS
        ubl_extensions = None

        for child in root:
            if child.tag == f"{{{ext_ns_prefix}}}UBLExtensions":
                ubl_extensions = child
                break

        if ubl_extensions is None:
            ubl_extensions = ET.SubElement(root, f"{{{ext_ns_prefix}}}UBLExtensions")
            root.insert(0, ubl_extensions)

        ext_content = None
        for ext in ubl_extensions:
            for content in ext:
                if content.tag == f"{{{ext_ns_prefix}}}ExtensionContent":
                    ext_content = content
                    break
            if ext_content is not None:
                break

        if ext_content is not None:
            ext_content.append(sig_element)
        else:
            new_ext = ET.SubElement(ubl_extensions, f"{{{ext_ns_prefix}}}UBLExtension")
            new_content = ET.SubElement(new_ext, f"{{{ext_ns_prefix}}}ExtensionContent")
            new_content.append(sig_element)
