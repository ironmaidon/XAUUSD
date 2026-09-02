import pytest
from pydantic import ValidationError

from bos.config import Mode, Settings, load_settings


def test_defaults_are_paper_and_disarmed() -> None:
    settings = Settings()
    assert settings.mode is Mode.PAPER
    assert settings.armed is False
    assert settings.live.live_trading is False


def test_live_requires_explicit_environment_gate() -> None:
    with pytest.raises(ValidationError, match="LIVE mode requires"):
        Settings(mode=Mode.LIVE)


def test_startup_always_resets_arm() -> None:
    assert Settings(armed=True).armed is False


def test_secret_is_not_rendered() -> None:
    settings = Settings(exchange={"api_secret": "top-secret"})
    assert "top-secret" not in repr(settings)


def test_delta_credentials_use_required_environment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DELTA_API_KEY", "key")
    monkeypatch.setenv("DELTA_API_SECRET", "secret")
    settings = load_settings()
    assert settings.exchange.api_key is not None
    assert settings.exchange.api_key.get_secret_value() == "key"
