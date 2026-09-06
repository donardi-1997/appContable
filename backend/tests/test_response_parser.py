import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.dian.response_parser import parse_dian_response


def test_parse_empty_response():
    result = parse_dian_response(None)
    assert result["status_code"] == "ERROR"
    assert "respuesta" in result["status_message"].lower() or "vacía" in result["status_message"].lower()
    assert len(result["errors"]) > 0


def test_parse_empty_string():
    result = parse_dian_response("")
    assert result["status_code"] == "ERROR"


def test_parse_valid_response():
    raw = """
    <soap:Envelope>
        <soap:Body>
            <GetStatusZipResponse>
                <StatusCode>00</StatusCode>
                <StatusMessage>Documento aceptado</StatusMessage>
                <ReferenceID>ABC123</ReferenceID>
                <AcceptanceDate>2026-01-15</AcceptanceDate>
            </GetStatusZipResponse>
        </soap:Body>
    </soap:Envelope>
    """
    result = parse_dian_response(raw)
    assert result["status_code"] == "00"
    assert result["reference_id"] == "ABC123"
    assert result["acceptance_date"] == "2026-01-15"


def test_parse_with_errors():
    raw = """
    <soap:Envelope>
        <soap:Body>
            <Response>
                <ErrorMessage>Error de formato</ErrorMessage>
                <ErrorMessage>Campo faltante</ErrorMessage>
            </Response>
        </soap:Body>
    </soap:Envelope>
    """
    result = parse_dian_response(raw)
    assert len(result["errors"]) == 2


def test_parse_soap_fault():
    raw = """
    <soap:Envelope>
        <soap:Body>
            <soap:Fault>
                <faultstring>Error interno del servidor</faultstring>
            </soap:Fault>
        </soap:Body>
    </soap:Envelope>
    """
    result = parse_dian_response(raw)
    assert result["status_code"] == "SOAP_FAULT"
    assert "servidor" in result["status_message"].lower()
