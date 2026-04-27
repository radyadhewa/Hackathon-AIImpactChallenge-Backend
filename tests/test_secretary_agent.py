import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.secretary_agent import SecretaryAgentService
from app.core.config import Settings
from app.main import create_app
from app.services.chat_service import ChatService
from app.services.context_bank import ContextBankService
from app.services.llm import BaseRuntime, EmbeddingService
from app.services.azure_search import AzureSearchContextBankIndex


class ScriptedRuntime(BaseRuntime):
    def __init__(self, responses: dict[str, dict]) -> None:
        self._responses = responses

    @property
    def name(self) -> str:
        return "scripted-runtime"

    async def generate(self, agent_name: str, instructions: str, payload: str) -> str:
        return json.dumps(self._responses.get(agent_name, {"error": "Unknown agent"}))


def build_test_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        context_bank_dir=tmp_path / "context_bank",
        use_microsoft_agent_framework=False,
    )
    runtime = ScriptedRuntime(
        responses={
            "chat_summarizer": {
                "summary": "Discussed project timeline and assigned tasks to team members.",
                "key_points": ["Timeline is tight", "Need more resources"],
                "decisions_made": ["Use Next.js for frontend"],
                "action_items": [
                    {
                        "content": "Create wireframes for landing page",
                        "assignee": "Rafi",
                        "due_date": None,
                        "priority": "high",
                    },
                    {
                        "content": "Set up project repository",
                        "assignee": "Dina",
                        "due_date": "2025-05-01",
                        "priority": "medium",
                    },
                ],
                "blockers": [],
                "sentiment": "positive",
            },
            "mom_generator": {
                "agenda": ["Project kickoff", "Timeline review", "Role assignments"],
                "key_discussions": [
                    "Project kickoff: Team introduced themselves and discussed project goals",
                    "Timeline review: Reviewed 6-week timeline with key milestones",
                ],
                "decisions_made": [
                    "Use Next.js for frontend development",
                    "Weekly sync meetings every Monday",
                ],
                "action_items": [
                    {
                        "content": "Create wireframes for all pages",
                        "assignee": "Rafi",
                        "due_date": "2025-05-05",
                        "priority": "high",
                    },
                ],
                "next_meeting": {
                    "suggested_date": "2025-05-05",
                    "agenda_preview": ["Review wireframes", "Discuss technical architecture"],
                },
            },
            "chatbot_assistant": {
                "suggestions": [
                    "Thanks for the update! I'll review the timeline and get back to you by EOD.",
                    "Got it, let me check my schedule and confirm.",
                    "Noted. Will follow up soon.",
                ],
                "reasoning": "The conversation is professional and requires a commitment to follow up.",
                "tone_analysis": "Professional, collaborative, slightly urgent",
            },
        }
    )
    context_bank = ContextBankService(
        root_dir=settings.context_bank_dir,
        embedding_service=EmbeddingService(settings),
        search_index=AzureSearchContextBankIndex(settings),
    )
    chat_service = ChatService(root_dir=settings.context_bank_dir)
    secretary_service = SecretaryAgentService(
        runtime=runtime,
        chat_service=chat_service,
        context_bank=context_bank,
    )
    app = create_app(settings=settings, secretary_service=secretary_service)
    return TestClient(app)


def test_conversation_flow(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    create_response = client.post(
        "/api/v1/secretary/conversations",
        json={
            "project_id": "proj-chat",
            "conversation_type": "project_channel",
            "title": "Project Discussion",
            "participants": ["Dina", "Rafi"],
        },
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["conversation"]["conversation_id"]

    list_response = client.get("/api/v1/secretary/projects/proj-chat/conversations")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    message1_response = client.post(
        "/api/v1/secretary/messages",
        json={
            "conversation_id": conversation_id,
            "sender_type": "freelancer",
            "sender_id": "user-dina",
            "sender_name": "Dina",
            "content": "Hi team! When should we start the frontend work?",
        },
    )
    assert message1_response.status_code == 200
    assert message1_response.json()["message"]["sender_name"] == "Dina"

    message2_response = client.post(
        "/api/v1/secretary/messages",
        json={
            "conversation_id": conversation_id,
            "sender_type": "freelancer",
            "sender_id": "user-rafi",
            "sender_name": "Rafi",
            "content": "I think we should use Next.js. I'll create the wireframes by next week.",
        },
    )
    assert message2_response.status_code == 200

    history_response = client.post(
        "/api/v1/secretary/chat/history",
        json={
            "conversation_id": conversation_id,
            "limit": 10,
        },
    )
    assert history_response.status_code == 200
    assert len(history_response.json()["messages"]) == 2


def test_chat_summarization_creates_events(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    create_response = client.post(
        "/api/v1/secretary/conversations",
        json={
            "project_id": "proj-summary",
            "conversation_type": "project_channel",
            "title": "Sprint Planning",
            "participants": ["Dina", "Rafi"],
        },
    )
    conversation_id = create_response.json()["conversation"]["conversation_id"]

    client.post(
        "/api/v1/secretary/messages",
        json={
            "conversation_id": conversation_id,
            "sender_type": "freelancer",
            "sender_id": "user-dina",
            "sender_name": "Dina",
            "content": "Let's discuss the timeline for this sprint.",
        },
    )
    client.post(
        "/api/v1/secretary/messages",
        json={
            "conversation_id": conversation_id,
            "sender_type": "freelancer",
            "sender_id": "user-rafi",
            "sender_name": "Rafi",
            "content": "I can create the wireframes. Dina, can you set up the repo?",
        },
    )

    summarize_response = client.post(
        "/api/v1/secretary/chat/summarize",
        json={
            "project_id": "proj-summary",
            "conversation_id": conversation_id,
            "create_action_items": True,
        },
    )
    assert summarize_response.status_code == 200
    result = summarize_response.json()
    assert "summary" in result
    assert len(result["events_created"]) > 0
    assert result["events_created"][0]["event_type"] == "task_created"


def test_meeting_workflow(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    meeting_response = client.post(
        "/api/v1/secretary/meetings",
        json={
            "project_id": "proj-meeting",
            "title": "Sprint Kickoff",
            "scheduled_at": "2025-05-01T10:00:00Z",
            "duration_minutes": 60,
            "participants": ["Dina", "Rafi"],
        },
    )
    assert meeting_response.status_code == 200
    meeting_id = meeting_response.json()["meeting"]["meeting_id"]

    list_response = client.get("/api/v1/secretary/projects/proj-meeting/meetings")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    transcript = """
    Dina: Welcome everyone to the sprint kickoff.
    Rafi: Thanks. I think we should use Next.js for the frontend.
    Dina: Agreed. I'll set up the repository this week.
    Rafi: And I'll work on the wireframes.
    Dina: Let's meet again next Monday to review.
    """

    complete_response = client.post(
        f"/api/v1/secretary/meetings/{meeting_id}/complete",
        json={
            "project_id": "proj-meeting",
            "transcript": transcript,
            "absentees": [],
        },
    )
    assert complete_response.status_code == 200
    result = complete_response.json()
    assert "mom" in result
    assert len(result["events_created"]) > 0


def test_secretary_suggest(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    create_response = client.post(
        "/api/v1/secretary/conversations",
        json={
            "project_id": "proj-suggest",
            "conversation_type": "direct",
            "title": "Direct Message",
            "participants": ["Dina", "Client"],
        },
    )
    conversation_id = create_response.json()["conversation"]["conversation_id"]

    client.post(
        "/api/v1/secretary/messages",
        json={
            "conversation_id": conversation_id,
            "sender_type": "client",
            "sender_id": "user-client",
            "sender_name": "Client",
            "content": "Can you send me the latest progress update?",
        },
    )

    suggest_response = client.post(
        "/api/v1/secretary/suggest",
        json={
            "project_id": "proj-suggest",
            "conversation_id": conversation_id,
            "current_message": "Sure, I will",
            "context_messages": 5,
        },
    )
    assert suggest_response.status_code == 200
    result = suggest_response.json()
    assert len(result["suggestions"]) > 0
    assert "reasoning" in result
