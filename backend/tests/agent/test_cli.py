import pytest

from agent import cli
from sentinel.core.config import Settings


def test_refuses_to_start_without_agent_model(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None, agent_model=""))

    assert cli.main(["do something"]) == 2
    assert "AGENT_MODEL is empty" in capsys.readouterr().err


def test_reports_unreachable_gateway(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings(_env_file=None, agent_model="test-model")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    async def fake_run_agent(*args: object, **kwargs: object) -> None:
        raise cli.GatewayUnavailable("Sentinel gateway unreachable at http://127.0.0.1:8000")

    monkeypatch.setattr(cli, "run_agent", fake_run_agent)

    assert cli.main(["do something"]) == 1
    assert "Sentinel gateway unreachable" in capsys.readouterr().err


def test_reports_missing_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None, agent_model="m"))

    async def fake_run_agent(*args: object, **kwargs: object) -> None:
        raise TypeError('"Could not resolve authentication method. Expected one of api_key"')

    monkeypatch.setattr(cli, "run_agent", fake_run_agent)

    assert cli.main(["do something"]) == 1
    assert "No Anthropic credentials found" in capsys.readouterr().err
