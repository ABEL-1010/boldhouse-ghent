import pytest
from fastapi.testclient import TestClient

from sentinel.core.config import Settings
from sentinel.main import create_app

TEST_ORIGIN = "http://localhost:3000"


@pytest.fixture
def client() -> TestClient:
    # _env_file=None keeps tests independent of the developer's local .env.
    settings = Settings(_env_file=None, cors_origins=[TEST_ORIGIN])
    return TestClient(create_app(settings))
