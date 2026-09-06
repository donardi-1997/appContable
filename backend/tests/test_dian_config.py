import sys
import os
from dataclasses import fields

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app.services.dian.config import DIANConfig
from app.services.dian.errors import DianConfigurationError


@pytest.fixture
def clean_env(monkeypatch):
    for f in fields(DIANConfig):
        if f.name not in ("habilitacion_soap_url", "produccion_soap_url", "resolution_prefix"):
            monkeypatch.delenv(f"DIAN_{f.name.upper()}", raising=False)
    monkeypatch.delenv("ELECTRONIC_INVOICE_PROVIDER", raising=False)
    monkeypatch.delenv("DIAN_ENVIRONMENT", raising=False)


@pytest.fixture
def config_no_env(clean_env):
    return DIANConfig()


def test_config_defaults(config_no_env):
    cfg = config_no_env
    assert cfg.provider == "mock"
    assert cfg.environment == "habilitacion"
    assert cfg.resolution_prefix == "FE"
    assert cfg.habilitacion_soap_url.startswith("https://")
    assert cfg.produccion_soap_url.startswith("https://")


def test_config_validate_not_dian(clean_env):
    cfg = DIANConfig(provider="mock")
    cfg.validate()


def test_config_validate_missing_fields(clean_env):
    cfg = DIANConfig(provider="dian")
    with pytest.raises(DianConfigurationError):
        cfg.validate()


def test_config_validate_habilitacion_needs_test_set(monkeypatch, clean_env):
    monkeypatch.setenv("DIAN_SOFTWARE_ID", "app-001")
    monkeypatch.setenv("DIAN_SOFTWARE_PIN", "1234")
    monkeypatch.setenv("DIAN_CERTIFICATE_PATH", "/cert.pfx")
    monkeypatch.setenv("DIAN_CERTIFICATE_PASSWORD", "pass")
    monkeypatch.setenv("DIAN_NIT", "900123456")
    monkeypatch.setenv("DIAN_RESOLUTION_NUMBER", "12345")
    monkeypatch.setenv("DIAN_RESOLUTION_FROM", "1")
    monkeypatch.setenv("DIAN_RESOLUTION_TO", "1000")
    monkeypatch.setenv("DIAN_RESOLUTION_START_DATE", "2026-01-01")
    monkeypatch.setenv("DIAN_RESOLUTION_END_DATE", "2026-12-31")
    monkeypatch.setenv("DIAN_ENVIRONMENT", "habilitacion")
    monkeypatch.delenv("DIAN_TEST_SET_ID", raising=False)

    cfg = DIANConfig(provider="dian")
    with pytest.raises(DianConfigurationError, match="TEST_SET_ID"):
        cfg.validate()


def test_get_soap_url_habilitacion(clean_env):
    cfg = DIANConfig(environment="habilitacion")
    url = cfg.get_soap_url()
    assert "habilitacion" in url.lower()


def test_get_soap_url_produccion(clean_env):
    cfg = DIANConfig(environment="produccion")
    url = cfg.get_soap_url()
    assert "produccion" in url.lower() or "dian" in url.lower()
