from sentinel.core.config import Settings


def test_cors_origins_parses_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, http://127.0.0.1:3000")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
