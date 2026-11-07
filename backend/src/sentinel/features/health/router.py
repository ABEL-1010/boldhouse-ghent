from fastapi import APIRouter

from sentinel import __version__
from sentinel.features.health.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", service="sentinel", version=__version__)
