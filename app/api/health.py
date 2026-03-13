"""Health check API endpoints."""

import time

from fastapi import APIRouter, Depends

from app.models.api_models import HealthCheckResponse
from app.config import settings
from app.core.dependencies import get_db_pool, get_cache_service
from app.services.database.postgres import DatabasePool
from app.services.cache.cache_service import CacheService
from app.services.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    db: DatabasePool = Depends(get_db_pool),
    cache: CacheService = Depends(get_cache_service),
) -> HealthCheckResponse:
    """
    Check the health of the API and its dependencies.

    Returns status of database, cache, and overall health.
    """
    start_time = time.time()

    # Check database
    db_status = "unknown"
    try:
        db_health = await db.health_check()
        db_status = "healthy" if db_health.get("healthy") else "unhealthy"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"
        logger.warning("health_db_error", error=str(e))

    # Check cache
    cache_status = "unknown"
    try:
        cache_health = await cache.health_check()
        cache_status = cache_health.get("status", "unknown")
    except Exception as e:
        cache_status = f"error: {str(e)[:50]}"
        logger.warning("health_cache_error", error=str(e))

    # Calculate overall health
    healthy = db_status == "healthy"
    status = "healthy" if healthy else "degraded"

    latency_ms = int((time.time() - start_time) * 1000)

    return HealthCheckResponse(
        healthy=healthy,
        status=status,
        database=db_status,
        cache=cache_status,
        latency_ms=latency_ms,
        version=settings.app_version,
    )


@router.get("/health/live")
async def liveness_check() -> dict:
    """
    Simple liveness check for Kubernetes/container orchestration.

    Returns 200 if the service is running.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_check(
    db: DatabasePool = Depends(get_db_pool),
) -> dict:
    """
    Readiness check - verifies the service can handle requests.

    Returns 200 if database is accessible.
    """
    try:
        health = await db.health_check()
        if health.get("healthy"):
            return {"status": "ready"}
        else:
            return {"status": "not_ready", "reason": "database_unhealthy"}
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        return {"status": "not_ready", "reason": str(e)[:100]}
