from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.database.repositories import get_setting, set_setting, record_audit_event
from app.schemas.model import (
    ModelStatusResponse,
    ModelConfigUpdate,
    ConnectionTestRequest,
    ConnectionTestResponse
)
from app.core.config import settings
from app.core.security import mask_secret
from app.providers.ollama_provider import ollama_provider
from app.providers.groq_provider import groq_provider
from app.observability.telemetry import telemetry

router = APIRouter(prefix="/models", tags=["Models & Providers"])

@router.get("/status", response_model=ModelStatusResponse)
async def get_models_status():
    ollama_health = await ollama_provider.check_health()
    groq_health = await groq_provider.check_health()
    metrics = telemetry.get_system_metrics()

    return ModelStatusResponse(
        local_runtime="Ollama",
        local_available=ollama_health.get("available", False),
        installed_models=ollama_health.get("installed_models", []),
        default_local_model=settings.LOCAL_MODEL_NAME,
        active_local_model=settings.LOCAL_MODEL_NAME if ollama_health.get("model_installed") else None,
        groq_available=groq_health.get("available", False),
        groq_masked_key=groq_health.get("masked_key", "NOT_CONFIGURED"),
        groq_reasoning_model=settings.GROQ_REASONING_MODEL,
        groq_fast_model=settings.GROQ_FAST_MODEL,
        allow_remote_fallback=settings.ALLOW_REMOTE_FALLBACK,
        require_fallback_confirmation=settings.REQUIRE_FALLBACK_CONFIRMATION,
        current_free_ram_mb=metrics["free_ram_mb"],
        ram_warning=metrics["ram_warning"]
    )

@router.put("/config")
async def update_models_config(req: ModelConfigUpdate, db: Session = Depends(get_db)):
    if req.local_model_name:
        settings.LOCAL_MODEL_NAME = req.local_model_name
        set_setting(db, "LOCAL_MODEL_NAME", req.local_model_name)
    if req.groq_api_key:
        settings.GROQ_API_KEY = req.groq_api_key.strip()
        record_audit_event(db, "GROQ_KEY_UPDATED", details={"masked": mask_secret(req.groq_api_key)})
    if req.groq_reasoning_model:
        settings.GROQ_REASONING_MODEL = req.groq_reasoning_model
        set_setting(db, "GROQ_REASONING_MODEL", req.groq_reasoning_model)
    if req.allow_remote_fallback is not None:
        settings.ALLOW_REMOTE_FALLBACK = req.allow_remote_fallback
        set_setting(db, "ALLOW_REMOTE_FALLBACK", req.allow_remote_fallback)
    if req.require_fallback_confirmation is not None:
        settings.REQUIRE_FALLBACK_CONFIRMATION = req.require_fallback_confirmation
        set_setting(db, "REQUIRE_FALLBACK_CONFIRMATION", req.require_fallback_confirmation)

    return {"message": "Model configuration updated successfully."}

@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_provider_connection(req: ConnectionTestRequest):
    if req.provider.lower() == "ollama":
        res = await ollama_provider.check_health(force_refresh=True)
        return ConnectionTestResponse(
            provider="ollama",
            success=res.get("available", False),
            latency_ms=0,
            message="Ollama connected." if res.get("available") else res.get("message", "Offline")
        )
    elif req.provider.lower() == "groq":
        res = await groq_provider.check_health(force_refresh=True)
        return ConnectionTestResponse(
            provider="groq",
            success=res.get("available", False),
            latency_ms=res.get("latency_ms", 0),
            message=res.get("message", "Groq tested.")
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{req.provider}'")
