from fastapi import APIRouter, Depends, Request

from app.agents.secretary_agent import SecretaryAgentService
from app.models.api import (
    ChatHistoryRequest,
    ChatHistoryResponse,
    ChatSummarizeRequest,
    ChatSummarizeResponse,
    ConversationCreateRequest,
    ConversationResponse,
    MeetingCompleteRequest,
    MeetingCompleteResponse,
    MeetingCreateRequest,
    MeetingResponse,
    MessageResponse,
    MessageSendRequest,
    SecretarySuggestRequest,
    SecretarySuggestResponse,
)
from app.models.domain import Conversation, Meeting

router = APIRouter(prefix="/secretary", tags=["Secretary Agent"])


def get_secretary_service(request: Request) -> SecretaryAgentService:
    return request.app.state.secretary_service


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    payload: ConversationCreateRequest,
    service: SecretaryAgentService = Depends(get_secretary_service),
) -> ConversationResponse:
    return await service.create_conversation(payload)


@router.get("/projects/{project_id}/conversations")
async def list_conversations(
    project_id: str,
    service: SecretaryAgentService = Depends(get_secretary_service),
) -> list[Conversation]:
    return await service.list_conversations(project_id)


@router.post("/messages", response_model=MessageResponse)
async def send_message(
    payload: MessageSendRequest,
    service: SecretaryAgentService = Depends(get_secretary_service),
) -> MessageResponse:
    return await service.send_message(payload)


@router.post("/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    payload: ChatHistoryRequest,
    service: SecretaryAgentService = Depends(get_secretary_service),
) -> ChatHistoryResponse:
    return await service.get_chat_history(payload)


@router.post("/chat/summarize", response_model=ChatSummarizeResponse)
async def summarize_chat(
    payload: ChatSummarizeRequest,
    service: SecretaryAgentService = Depends(get_secretary_service),
) -> ChatSummarizeResponse:
    return await service.summarize_chat(payload)


@router.post("/meetings", response_model=MeetingResponse)
async def create_meeting(
    payload: MeetingCreateRequest,
    service: SecretaryAgentService = Depends(get_secretary_service),
) -> MeetingResponse:
    return await service.create_meeting(payload)


@router.get("/projects/{project_id}/meetings")
async def list_meetings(
    project_id: str,
    status: str | None = None,
    service: SecretaryAgentService = Depends(get_secretary_service),
) -> list[Meeting]:
    return await service.list_meetings(project_id, status)


@router.post("/projects/{project_id}/meetings/{meeting_id}/complete", response_model=MeetingCompleteResponse)
async def complete_meeting(
    project_id: str,
    meeting_id: str,
    payload: MeetingCompleteRequest,
    service: SecretaryAgentService = Depends(get_secretary_service),
) -> MeetingCompleteResponse:
    return await service.complete_meeting(project_id, meeting_id, payload)


@router.post("/suggest", response_model=SecretarySuggestResponse)
async def suggest_response(
    payload: SecretarySuggestRequest,
    service: SecretaryAgentService = Depends(get_secretary_service),
) -> SecretarySuggestResponse:
    return await service.suggest_response(payload)
