import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.pm_agent import PMAgentService
from app.core.config import Settings
from app.main import create_app
from app.services.azure_search import AzureSearchContextBankIndex
from app.services.context_bank import ContextBankService
from app.services.llm import BaseRuntime, EmbeddingService
from app.services.timeline_service import TimelineService


class ScriptedRuntime(BaseRuntime):
    def __init__(self, responses: dict[str, dict]) -> None:
        self._responses = responses

    @property
    def name(self) -> str:
        return "scripted-runtime"

    async def generate(self, agent_name: str, instructions: str, payload: str) -> str:
        return json.dumps(self._responses[agent_name])


def build_test_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        context_bank_dir=tmp_path / "context_bank",
        use_microsoft_agent_framework=False,
    )
    runtime = ScriptedRuntime(
        responses={
            "task_breakdown": {
                "summary": "Plan the work across the micro-agency.",
                "assumptions": ["Scope is stable for one sprint."],
                "tasks": [
                    {
                        "task_id": "TASK-1",
                        "title": "Create landing page shell",
                        "description": "Build the responsive shell for the landing page.",
                        "assigned_to": "Dina",
                        "estimated_hours": 10,
                        "priority": "high",
                        "due_hint": "This week",
                        "dependencies": [],
                        "acceptance_criteria": ["Responsive on mobile and desktop"],
                        "recommended_references": ["Client brief"],
                    }
                ],
            },
            "work_checker": {
                "verdict": "revise",
                "scope_alignment_score": 68,
                "summary": "Good start, but the artifact needs tighter mapping to scope.",
                "strengths": ["Structure is clear."],
                "gaps": ["Missing explicit CMS handoff notes."],
                "improvement_actions": ["Add CMS handoff section."],
                "reference_suggestions": ["Review the scope reference again."],
                "needs_escalation": False,
                "escalation_message": None,
            },
            "reporter": {
                "summary": "Project is moving with early planning momentum.",
                "progress_percent": 35,
                "overall_status": "watch",
                "wins": ["Task plan is created."],
                "blockers": [],
                "upcoming_actions": ["Review first frontend deliverable."],
                "risks": ["Need more project updates from freelancers."],
                "escalations": [],
                "morale_coaching": ["Keep documenting async decisions."],
            },
        }
    )
    context_bank = ContextBankService(
        root_dir=settings.context_bank_dir,
        embedding_service=EmbeddingService(settings),
        search_index=AzureSearchContextBankIndex(settings),
    )
    timeline_service = TimelineService(context_bank)
    pm_service = PMAgentService(runtime=runtime, context_bank=context_bank, timeline_service=timeline_service)
    app = create_app(settings=settings, pm_service=pm_service)
    return TestClient(app)


def test_pm_agent_endpoints(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    bootstrap_response = client.post(
        "/api/v1/pm/projects/bootstrap",
        json={
            "overview": {
                "project_id": "proj-1",
                "project_name": "Keroyok Demo",
                "description": "Build a marketplace MVP.",
                "scope": "Planning, frontend, QA, and handoff.",
                "success_criteria": ["Async-ready workflow"],
                "constraints": ["Small budget"],
                "freelancers": [
                    {
                        "name": "Dina",
                        "role": "Frontend Engineer",
                        "hours_per_week": 20,
                        "timezone": "Asia/Jakarta",
                        "skills": ["Next.js"],
                    }
                ],
                "milestones": [],
            }
        },
    )
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["snapshot"]["overview"]["project_id"] == "proj-1"

    health_response = client.get("/api/v1/pm/health")
    assert health_response.status_code == 200
    assert "log_store" in health_response.json()

    update_response = client.post(
        "/api/v1/pm/projects/proj-1/updates",
        json={
            "title": "Kickoff completed",
            "content": "Client confirmed the MVP scope and launch urgency.",
            "tags": ["kickoff"],
        },
    )
    assert update_response.status_code == 200

    breakdown_response = client.post(
        "/api/v1/pm/task-breakdown",
        json={
            "project_id": "proj-1",
            "delivery_goal": "Launch MVP",
            "source_material": "Need responsive pages, clear backlog, and CMS handoff.",
        },
    )
    assert breakdown_response.status_code == 200
    assert breakdown_response.json()["result"]["tasks"][0]["assigned_to"] == "Dina"

    work_check_response = client.post(
        "/api/v1/pm/work-check",
        json={
            "project_id": "proj-1",
            "task_id": "TASK-1",
            "task_title": "Create landing page shell",
            "freelancer_name": "Dina",
            "scope_reference": "Responsive landing page plus CMS handoff notes.",
            "deliverable_summary": "Responsive page shell complete.",
            "deliverable_artifact": "Responsive landing page shell is done but CMS handoff notes are missing.",
        },
    )
    assert work_check_response.status_code == 200
    assert work_check_response.json()["result"]["verdict"] == "revise"

    report_response = client.post(
        "/api/v1/pm/reports",
        json={
            "project_id": "proj-1",
            "cadence": "weekly",
        },
    )
    assert report_response.status_code == 200
    assert report_response.json()["result"]["overall_status"] == "watch"

    context_response = client.get("/api/v1/pm/projects/proj-1/context")
    assert context_response.status_code == 200
    assert len(context_response.json()["snapshot"]["recent_entries"]) >= 4


def test_timeline_endpoints(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    client.post(
        "/api/v1/pm/projects/bootstrap",
        json={
            "overview": {
                "project_id": "proj-timeline",
                "project_name": "Timeline Test Project",
                "description": "Test project for timeline features.",
                "scope": "Testing timeline generation.",
                "freelancers": [
                    {
                        "name": "Rafi",
                        "role": "Designer",
                        "hours_per_week": 15,
                        "timezone": "Asia/Jakarta",
                        "skills": ["Figma"],
                    }
                ],
            }
        },
    )

    client.post(
        "/api/v1/pm/task-breakdown",
        json={
            "project_id": "proj-timeline",
            "delivery_goal": "Design system",
            "source_material": "Create a component library.",
        },
    )

    generate_response = client.post(
        "/api/v1/pm/timeline/generate",
        json={"project_id": "proj-timeline"},
    )
    assert generate_response.status_code == 200
    timeline_data = generate_response.json()["timeline"]
    assert timeline_data["project_id"] == "proj-timeline"
    assert len(timeline_data["entries"]) > 0
    assert "critical_path" in timeline_data

    get_response = client.get("/api/v1/pm/projects/proj-timeline/timeline")
    assert get_response.status_code == 200
    assert get_response.json()["timeline"]["project_id"] == "proj-timeline"


def test_task_status_update(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    client.post(
        "/api/v1/pm/projects/bootstrap",
        json={
            "overview": {
                "project_id": "proj-status",
                "project_name": "Status Test",
                "description": "Test task status updates.",
                "scope": "Testing status workflow.",
                "freelancers": [{"name": "Dina", "role": "Dev", "hours_per_week": 20, "timezone": "UTC", "skills": []}],
            }
        },
    )

    client.post(
        "/api/v1/pm/task-breakdown",
        json={
            "project_id": "proj-status",
            "delivery_goal": "Build feature",
            "source_material": "Implement auth.",
        },
    )

    client.post("/api/v1/pm/timeline/generate", json={"project_id": "proj-status"})

    update_response = client.post(
        "/api/v1/pm/projects/proj-status/tasks/TASK-1/status",
        json={"status": "in_progress", "actual_hours": 5},
    )
    assert update_response.status_code == 200

    complete_response = client.post(
        "/api/v1/pm/projects/proj-status/tasks/TASK-1/status",
        json={"status": "completed", "actual_hours": 10, "notes": "Done!"},
    )
    assert complete_response.status_code == 200

    events_response = client.get("/api/v1/pm/projects/proj-status/events")
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert len(events) > 0
    assert any(e["event_type"] == "task_completed" for e in events)


def test_escalation_creates_event(tmp_path: Path) -> None:
    settings = Settings(
        context_bank_dir=tmp_path / "context_bank",
        use_microsoft_agent_framework=False,
    )
    runtime = ScriptedRuntime(
        responses={
            "reporter": {
                "summary": "Project has critical issues.",
                "progress_percent": 20,
                "overall_status": "at_risk",
                "wins": [],
                "blockers": ["Scope creep"],
                "upcoming_actions": [],
                "risks": ["Timeline slip"],
                "escalations": ["Critical: Timeline at risk due to scope creep"],
                "morale_coaching": ["Focus on MVP."],
            }
        }
    )
    context_bank = ContextBankService(
        root_dir=settings.context_bank_dir,
        embedding_service=EmbeddingService(settings),
        search_index=AzureSearchContextBankIndex(settings),
    )
    timeline_service = TimelineService(context_bank)
    pm_service = PMAgentService(runtime=runtime, context_bank=context_bank, timeline_service=timeline_service)
    app = create_app(settings=settings, pm_service=pm_service)
    client = TestClient(app)

    client.post(
        "/api/v1/pm/projects/bootstrap",
        json={
            "overview": {
                "project_id": "proj-escalation",
                "project_name": "Escalation Test",
                "description": "Test escalation handling.",
                "scope": "Testing.",
                "freelancers": [],
            }
        },
    )

    report_response = client.post(
        "/api/v1/pm/reports",
        json={"project_id": "proj-escalation", "cadence": "weekly"},
    )
    assert report_response.status_code == 200

    events_response = client.get("/api/v1/pm/projects/proj-escalation/events")
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert len(events) > 0

    escalation_events = [e for e in events if e["event_type"] == "escalation"]
    assert len(escalation_events) > 0
    assert escalation_events[0]["target_agent"] == "pm_agent"

    event_id = escalation_events[0]["event_id"]
    resolve_response = client.post(
        f"/api/v1/pm/projects/proj-escalation/events/{event_id}/resolve",
        json={"resolved_by": "human_pm"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"
