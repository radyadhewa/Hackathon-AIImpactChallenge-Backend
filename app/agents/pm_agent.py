from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.agents.prompts import (
    REPORTER_INSTRUCTIONS,
    TASK_BREAKDOWN_INSTRUCTIONS,
    TIMELINE_GENERATION_INSTRUCTIONS,
    WORK_CHECKER_INSTRUCTIONS,
)
from app.models.api import (
    ContextRecordResponse,
    ProjectBootstrapRequest,
    ProjectContextResponse,
    ProjectEventsResponse,
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
from app.models.domain import (
    AgentEvent,
    ProjectReport,
    ProjectTimeline,
    TaskBreakdownResult,
    TaskItem,
    WorkCheckResult,
)
from app.services.context_bank import ContextBankService
from app.services.llm import BaseRuntime
from app.services.timeline_service import TimelineService

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


class PMAgentService:
    def __init__(
        self,
        runtime: BaseRuntime,
        context_bank: ContextBankService,
        timeline_service: TimelineService | None = None,
    ) -> None:
        self._runtime = runtime
        self._context_bank = context_bank
        self._timeline_service = timeline_service or TimelineService(context_bank)

    @property
    def runtime_name(self) -> str:
        return self._runtime.name

    @property
    def context_bank_name(self) -> str:
        return self._context_bank.name

    async def bootstrap_project(
        self,
        payload: ProjectBootstrapRequest,
    ) -> ProjectContextResponse:
        snapshot = await self._context_bank.bootstrap_project(payload.overview)
        return ProjectContextResponse(snapshot=snapshot)

    async def add_project_update(
        self,
        project_id: str,
        payload: ProjectUpdateRequest,
    ) -> ContextRecordResponse:
        await self._require_project(project_id)
        record = await self._context_bank.add_record(
            project_id=project_id,
            entry_type="project_update",
            title=payload.title,
            content=payload.content,
            tags=payload.tags,
            source=payload.source,
            metadata=payload.metadata,
        )
        return ContextRecordResponse(record=record)

    async def get_project_context(self, project_id: str) -> ProjectContextResponse:
        await self._require_project(project_id)
        snapshot = await self._context_bank.get_snapshot(project_id)
        return ProjectContextResponse(snapshot=snapshot)

    async def generate_task_breakdown(
        self,
        payload: TaskBreakdownRequest,
    ) -> TaskBreakdownResponse:
        overview = await self._require_project(payload.project_id)
        references = await self._context_bank.search_records(
            payload.project_id,
            f"{payload.delivery_goal} {payload.source_material}",
            limit=5,
        )
        prompt = json.dumps(
            {
                "project_overview": overview.model_dump(mode="json"),
                "delivery_goal": payload.delivery_goal,
                "source_material": payload.source_material,
                "freelancer_focus": payload.freelancer_focus,
                "references": [record.model_dump(mode="json") for record in references],
            }
        )
        raw = await self._runtime.generate(
            "task_breakdown",
            TASK_BREAKDOWN_INSTRUCTIONS,
            prompt,
        )
        result = TaskBreakdownResult.model_validate(self._parse_json(raw))
        record = await self._context_bank.add_record(
            project_id=payload.project_id,
            entry_type="task_breakdown",
            title=f"Task breakdown for {payload.delivery_goal}",
            content=result.model_dump_json(indent=2),
            tags=["pm", "planning", "task-breakdown"],
            metadata={"delivery_goal": payload.delivery_goal},
            source="task_breakdown_subagent",
        )
        return TaskBreakdownResponse(result=result, context_record=record)

    async def check_work(self, payload: WorkCheckRequest) -> WorkCheckResponse:
        overview = await self._require_project(payload.project_id)
        references = await self._context_bank.search_records(
            payload.project_id,
            f"{payload.task_title} {payload.scope_reference}",
            limit=5,
        )
        prompt = json.dumps(
            {
                "project_overview": overview.model_dump(mode="json"),
                "task_id": payload.task_id,
                "task_title": payload.task_title,
                "freelancer_name": payload.freelancer_name,
                "scope_reference": payload.scope_reference,
                "deliverable_summary": payload.deliverable_summary,
                "deliverable_artifact": payload.deliverable_artifact,
                "requester_notes": payload.requester_notes,
                "references": [record.model_dump(mode="json") for record in references],
            }
        )
        raw = await self._runtime.generate(
            "work_checker",
            WORK_CHECKER_INSTRUCTIONS,
            prompt,
        )
        result = WorkCheckResult.model_validate(self._parse_json(raw))
        record = await self._context_bank.add_record(
            project_id=payload.project_id,
            entry_type="work_check",
            title=f"Work check for {payload.task_id}",
            content=result.model_dump_json(indent=2),
            tags=["pm", "qa", "work-check"],
            metadata={"task_id": payload.task_id, "freelancer_name": payload.freelancer_name},
            source="work_checker_subagent",
        )
        return WorkCheckResponse(result=result, context_record=record)

    async def generate_report(self, payload: ReportRequest) -> ReportResponse:
        overview = await self._require_project(payload.project_id)
        recent_entries = await self._context_bank.list_records(payload.project_id, limit=12)
        prompt = json.dumps(
            {
                "project_overview": overview.model_dump(mode="json"),
                "cadence": payload.cadence,
                "days_since_last_report": payload.days_since_last_report,
                "requester_notes": payload.requester_notes,
                "recent_entries": [record.model_dump(mode="json") for record in recent_entries],
            }
        )
        raw = await self._runtime.generate(
            "reporter",
            REPORTER_INSTRUCTIONS,
            prompt,
        )
        result = ProjectReport.model_validate(self._parse_json(raw))
        record = await self._context_bank.add_record(
            project_id=payload.project_id,
            entry_type="report",
            title=f"{payload.cadence.title()} PM report",
            content=result.model_dump_json(indent=2),
            tags=["pm", "reporting", payload.cadence],
            metadata={"cadence": payload.cadence},
            source="reporter_subagent",
        )

        if result.escalations:
            for escalation in result.escalations:
                await self._context_bank.add_agent_event(
                    project_id=payload.project_id,
                    event=AgentEvent(
                        event_id=str(uuid.uuid4()),
                        project_id=payload.project_id,
                        source_agent="reporter_subagent",
                        event_type="escalation",
                        title=f"Escalation: {escalation[:100]}",
                        description=escalation,
                        target_agent="pm_agent",
                        metadata={
                            "report_cadence": payload.cadence,
                            "overall_status": result.overall_status,
                        },
                    ),
                )

        return ReportResponse(result=result, context_record=record)

    async def _require_project(self, project_id: str):
        overview = await self._context_bank.get_project_overview(project_id)
        if overview is None:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' was not found.")
        return overview

    async def generate_timeline(
        self,
        payload: TimelineGenerateRequest,
    ) -> TimelineResponse:
        overview = await self._require_project(payload.project_id)

        references = await self._context_bank.search_records(
            payload.project_id,
            "task breakdown plan",
            limit=5,
        )

        tasks = []
        for ref in references:
            if ref.entry_type == "task_breakdown":
                try:
                    data = json.loads(ref.content)
                    for task_data in data.get("tasks", []):
                        tasks.append(TaskBreakdownResult.model_validate(task_data))
                except Exception:
                    continue

        if not tasks:
            from datetime import datetime, timezone
            tasks = [
                TaskBreakdownResult(
                    summary="Initial project tasks",
                    tasks=[
                        TaskItem(
                            task_id="TASK-001",
                            title="Project kickoff",
                            description="Initial project setup and planning",
                            assigned_to=overview.freelancers[0].name if overview.freelancers else "TBD",
                            estimated_hours=8,
                            priority="high",
                            due_hint="Week 1",
                            dependencies=[],
                            acceptance_criteria=["Project scope defined"],
                        )
                    ],
                )
            ]

        from datetime import datetime, timezone
        start_date = None
        if payload.start_date:
            try:
                start_date = datetime.fromisoformat(payload.start_date.replace("Z", "+00:00"))
            except ValueError:
                start_date = datetime.now(timezone.utc)

        timeline = await self._timeline_service.create_timeline(
            payload.project_id,
            tasks[0].tasks if tasks else [],
            start_date=start_date,
        )

        record = await self._context_bank.add_record(
            project_id=payload.project_id,
            entry_type="timeline",
            title=f"Project timeline generated",
            content=timeline.model_dump_json(indent=2),
            tags=["pm", "timeline", "planning"],
            metadata={"entries_count": len(timeline.entries)},
            source="timeline_service",
        )

        return TimelineResponse(timeline=timeline, context_record=record)

    async def get_timeline(self, project_id: str) -> TimelineResponse:
        await self._require_project(project_id)
        timeline = await self._timeline_service.get_timeline(project_id)
        if timeline is None:
            raise HTTPException(status_code=404, detail=f"No timeline found for project '{project_id}'.")
        return TimelineResponse(timeline=timeline, context_record=None)

    async def update_task_status(
        self,
        project_id: str,
        task_id: str,
        payload: TaskStatusUpdateRequest,
    ) -> ContextRecordResponse:
        await self._require_project(project_id)

        entry = await self._timeline_service.update_entry_status(
            project_id,
            task_id,
            payload.status,
            payload.actual_hours,
        )

        if entry is None:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

        record = await self._context_bank.add_record(
            project_id=project_id,
            entry_type="task_status_update",
            title=f"Task {task_id} status updated to {payload.status}",
            content=json.dumps({
                "task_id": task_id,
                "status": payload.status,
                "actual_hours": payload.actual_hours,
                "notes": payload.notes,
            }),
            tags=["pm", "task-update", payload.status],
            metadata={"task_id": task_id, "status": payload.status},
            source="pm_agent",
        )

        if payload.status == "completed":
            await self._context_bank.add_agent_event(
                project_id=project_id,
                event=AgentEvent(
                    event_id=str(uuid.uuid4()),
                    project_id=project_id,
                    source_agent="pm_agent",
                    event_type="task_completed",
                    title=f"Task completed: {entry.title}",
                    description=f"Task {task_id} has been marked as completed.",
                    metadata={"task_id": task_id, "completed_by": entry.assigned_to},
                ),
            )

        return ContextRecordResponse(record=record)

    async def get_project_events(
        self,
        project_id: str,
        target_agent: str | None = None,
    ) -> ProjectEventsResponse:
        await self._require_project(project_id)
        events = await self._context_bank.get_agent_events(project_id, target_agent=target_agent)
        return ProjectEventsResponse(events=events)

    async def resolve_event(
        self,
        project_id: str,
        event_id: str,
        payload: ResolveEventRequest,
    ) -> dict:
        await self._require_project(project_id)
        event = await self._context_bank.resolve_agent_event(
            project_id,
            event_id,
            payload.resolved_by,
        )
        if event is None:
            raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found or already resolved.")
        return {"status": "resolved", "event_id": event_id}

    @staticmethod
    def _parse_json(raw_response: str) -> dict:
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            match = JSON_OBJECT_PATTERN.search(raw_response)
            if match:
                return json.loads(match.group(0))
        raise HTTPException(
            status_code=502,
            detail="Agent runtime did not return valid JSON.",
        )

