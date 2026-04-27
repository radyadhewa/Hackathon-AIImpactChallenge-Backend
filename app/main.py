from fastapi import FastAPI

from app.api.routes.pm_agent import router as pm_agent_router
from app.api.routes.secretary_agent import router as secretary_agent_router
from app.api.routes.talent_agent import router as talent_agent_router
from app.core.config import Settings, get_settings
from app.core.dependencies import build_pm_service, build_secretary_service, build_talent_service


def create_app(
    settings: Settings | None = None,
    pm_service=None,
    secretary_service=None,
    talent_service=None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_pm_service = pm_service or build_pm_service(resolved_settings)
    resolved_secretary_service = secretary_service or build_secretary_service(resolved_settings)
    resolved_talent_service = talent_service or build_talent_service(resolved_settings)

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.3.0",
        description="AI backend for Keroyok.AI - Agentic AI Talent Marketplace & Project Manager",
    )
    app.state.settings = resolved_settings
    app.state.pm_service = resolved_pm_service
    app.state.secretary_service = resolved_secretary_service
    app.state.talent_service = resolved_talent_service
    app.include_router(pm_agent_router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(secretary_agent_router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(talent_agent_router, prefix=resolved_settings.api_v1_prefix)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": resolved_settings.app_name,
            "environment": resolved_settings.app_env,
            "status": "ok",
            "agents": ["talent_agent", "pm_agent", "secretary_agent"],
            "version": "0.3.0",
        }

    return app


app = create_app()

