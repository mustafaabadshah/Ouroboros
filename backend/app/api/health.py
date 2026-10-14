from fastapi import APIRouter
from app.core.config import settings
from app.observability.telemetry import telemetry
from app.sandbox.detector import sandbox_detector
from app.providers.ollama_provider import ollama_provider
from app.providers.groq_provider import groq_provider

router = APIRouter(tags=["Health & System"])

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV
    }

@router.get("/system/status")
async def system_status():
    metrics = telemetry.get_system_metrics()
    sandbox = await sandbox_detector.detect_capabilities()
    ollama = await ollama_provider.check_health()
    groq = await groq_provider.check_health()

    return {
        "system": metrics,
        "sandbox": sandbox,
        "ollama": ollama,
        "groq": {
            "available": groq.get("available", False),
            "masked_key": groq.get("masked_key", "NOT_CONFIGURED"),
            "model": settings.GROQ_REASONING_MODEL
        }
    }
