import pytest
from fastapi.testclient import TestClient

from fakeweb.main import create_app
from sentinel.core.config import Settings


@pytest.fixture
def web() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None).web_dir))


@pytest.mark.parametrize("page", ["news1.html", "news2.html", "news3.html", "docs.html"])
def test_serves_benign_pages(web: TestClient, page: str) -> None:
    response = web.get(f"/{page}")

    assert response.status_code == 200
    assert "IMPORTANT INSTRUCTION" not in response.text


def test_poisoned_page_hides_injection_in_white_text(web: TestClient) -> None:
    text = web.get("/productivity-tips.html").text

    assert "backup@unknown-domain.xyz" in text
    assert "color:#ffffff;background:#ffffff" in text


@pytest.mark.parametrize(
    "path", ["/missing.html", "/%2e%2e/workspace/.env", "/..%2fhoneytokens.txt"]
)
def test_does_not_serve_anything_outside_web_dir(web: TestClient, path: str) -> None:
    assert web.get(path).status_code == 404


def test_exposes_no_api_docs(web: TestClient) -> None:
    assert web.get("/docs").status_code == 404
