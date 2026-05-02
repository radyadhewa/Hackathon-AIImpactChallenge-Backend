from fastapi import APIRouter, Depends, Request

from app.agents.pm_agent import PMAgentService
from app.models.api import (
    ContextRecordResponse,
    HealthResponse,
    ProjectBootstrapRequest,
    ProjectContextResponse,
    ProjectEventsResponse,
    PmLogListResponse,
    ProjectUpdateRequest,
    ReportRequest,
    ReportResponse,
    ResolveEventRequest,
    TaskBreakdownRequest,
    TaskBreakdownResponse,
    TaskStatusUpdateRequest,
    TimelineGenerateRequest,
    TimelineResponse,
    WorkCheckRequest,
    WorkCheckResponse,
)

router = APIRouter(prefix="/pm", tags=["PM Agent"])


def get_pm_service(request: Request) -> PMAgentService:
    return request.app.state.pm_service


@router.get("/health")
async def health(service: PMAgentService = Depends(get_pm_service)) -> dict:
    search_index = service._context_bank._search_index if hasattr(service, '_context_bank') else None
    azure_search_status = "not_available"
    if search_index:
        if search_index.enabled:
            azure_search_status = "connected" if search_index._index_ready else "configured_not_ready"
        else:
            azure_search_status = "disabled"

    settings = service._context_bank._settings if hasattr(service, '_context_bank') else None

    return {
        "status": "ok",
        "runtime": service.runtime_name,
        "context_bank": service.context_bank_name,
        "log_store": service.log_store_name,
        "azure_search": azure_search_status,
        "cors_origins": settings.cors_allowed_origin_list if settings else [],
    }


@router.post("/projects/bootstrap", response_model=ProjectContextResponse)
async def bootstrap_project(
    payload: ProjectBootstrapRequest,
    service: PMAgentService = Depends(get_pm_service),
) -> ProjectContextResponse:
    return await service.bootstrap_project(payload)


@router.post("/projects/{project_id}/updates", response_model=ContextRecordResponse)
async def add_project_update(
    project_id: str,
    payload: ProjectUpdateRequest,
    service: PMAgentService = Depends(get_pm_service),
) -> ContextRecordResponse:
    return await service.add_project_update(project_id, payload)


@router.get("/projects/{project_id}/context", response_model=ProjectContextResponse)
async def get_project_context(
    project_id: str,
    service: PMAgentService = Depends(get_pm_service),
) -> ProjectContextResponse:
    return await service.get_project_context(project_id)


@router.post("/task-breakdown", response_model=TaskBreakdownResponse)
async def task_breakdown(
    payload: TaskBreakdownRequest,
    service: PMAgentService = Depends(get_pm_service),
) -> TaskBreakdownResponse:
    return await service.generate_task_breakdown(payload)


@router.post("/work-check", response_model=WorkCheckResponse)
async def work_check(
    payload: WorkCheckRequest,
    service: PMAgentService = Depends(get_pm_service),
) -> WorkCheckResponse:
    return await service.check_work(payload)


@router.post("/reports", response_model=ReportResponse)
async def report(
    payload: ReportRequest,
    service: PMAgentService = Depends(get_pm_service),
) -> ReportResponse:
    return await service.generate_report(payload)


@router.post("/timeline/generate", response_model=TimelineResponse)
async def generate_timeline(
    payload: TimelineGenerateRequest,
    service: PMAgentService = Depends(get_pm_service),
) -> TimelineResponse:
    return await service.generate_timeline(payload)


@router.get("/projects/{project_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    project_id: str,
    service: PMAgentService = Depends(get_pm_service),
) -> TimelineResponse:
    return await service.get_timeline(project_id)


@router.post("/projects/{project_id}/tasks/{task_id}/status", response_model=ContextRecordResponse)
async def update_task_status(
    project_id: str,
    task_id: str,
    payload: TaskStatusUpdateRequest,
    service: PMAgentService = Depends(get_pm_service),
) -> ContextRecordResponse:
    return await service.update_task_status(project_id, task_id, payload)


@router.get("/projects/{project_id}/events", response_model=ProjectEventsResponse)
async def get_project_events(
    project_id: str,
    target_agent: str | None = None,
    service: PMAgentService = Depends(get_pm_service),
) -> ProjectEventsResponse:
    return await service.get_project_events(project_id, target_agent)


@router.get("/projects/{project_id}/logs", response_model=PmLogListResponse)
async def get_project_logs(
    project_id: str,
    action_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    service: PMAgentService = Depends(get_pm_service),
) -> PmLogListResponse:
    return await service.list_logs(
        project_id,
        action_type=action_type,
        limit=limit,
        offset=offset,
    )


@router.post("/projects/{project_id}/events/{event_id}/resolve")
async def resolve_event(
    project_id: str,
    event_id: str,
    payload: ResolveEventRequest,
    service: PMAgentService = Depends(get_pm_service),
) -> dict:
    return await service.resolve_event(project_id, event_id, payload)
