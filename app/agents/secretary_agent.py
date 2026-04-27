from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.agents.prompts import (
    CHAT_SUMMARIZER_INSTRUCTIONS,
    CHATBOT_ASSISTANT_INSTRUCTIONS,
    MOM_GENERATOR_INSTRUCTIONS,
)
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
from app.models.domain import (
    ActionItem,
    AgentEvent,
    ChatSummary,
    Conversation,
    Meeting,
    Message,
    MinutesOfMeeting,
)
from app.services.chat_service import ChatService
from app.services.context_bank import ContextBankService
from app.services.llm import BaseRuntime

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


class SecretaryAgentService:
    def __init__(
        self,
        runtime: BaseRuntime,
        chat_service: ChatService,
        context_bank: ContextBankService,
    ) -> None:
        self._runtime = runtime
        self._chat_service = chat_service
        self._context_bank = context_bank

    @property
    def runtime_name(self) -> str:
        return self._runtime.name

    async def create_conversation(
        self,
        payload: ConversationCreateRequest,
    ) -> ConversationResponse:
        conversation = await self._chat_service.create_conversation(
            project_id=payload.project_id,
            conversation_type=payload.conversation_type,
            title=payload.title,
            participants=payload.participants,
        )
        return ConversationResponse(conversation=conversation)

    async def send_message(
        self,
        payload: MessageSendRequest,
    ) -> MessageResponse:
        message = await self._chat_service.send_message(
            project_id=payload.project_id,
            conversation_id=payload.conversation_id,
            sender_type=payload.sender_type,
            sender_id=payload.sender_id,
            sender_name=payload.sender_name,
            content=payload.content,
            reply_to=payload.reply_to,
        )
        return MessageResponse(message=message)

    async def get_chat_history(
        self,
        payload: ChatHistoryRequest,
    ) -> ChatHistoryResponse:
        messages = await self._chat_service.get_messages(
            project_id=payload.project_id,
            conversation_id=payload.conversation_id,
            limit=payload.limit,
            before_message_id=payload.before_message_id,
        )
        return ChatHistoryResponse(
            messages=messages,
            has_more=len(messages) == payload.limit,
        )

    async def summarize_chat(
        self,
        payload: ChatSummarizeRequest,
    ) -> ChatSummarizeResponse:
        conversation = await self._chat_service.get_conversation(
            payload.project_id,
            payload.conversation_id,
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = await self._chat_service.get_messages(
            project_id=payload.project_id,
            conversation_id=payload.conversation_id,
            limit=payload.message_count or 50,
        )

        if not messages:
            raise HTTPException(status_code=400, detail="No messages to summarize")

        messages.reverse()

        prompt = json.dumps({
            "conversation_title": conversation.title,
            "participants": conversation.participants,
            "messages": [
                {
                    "sender": m.sender_name,
                    "sender_type": m.sender_type,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in messages
            ],
        })

        raw = await self._runtime.generate(
            "chat_summarizer",
            CHAT_SUMMARIZER_INSTRUCTIONS,
            prompt,
        )

        result = self._parse_json(raw)

        action_items: list[ActionItem] = []
        for item_data in result.get("action_items", []):
            action_item = ActionItem(
                item_id=str(uuid.uuid4()),
                conversation_id=payload.conversation_id,
                project_id=payload.project_id,
                content=item_data["content"],
                assignee=item_data.get("assignee"),
                priority=item_data.get("priority", "medium"),
                source_type="chat",
            )
            action_items.append(action_item)

        summary = ChatSummary(
            summary_id=str(uuid.uuid4()),
            conversation_id=payload.conversation_id,
            project_id=payload.project_id,
            summary=result["summary"],
            key_points=result.get("key_points", []),
            decisions_made=result.get("decisions_made", []),
            action_items=action_items,
            participants=conversation.participants,
            message_count=len(messages),
            from_timestamp=messages[0].timestamp,
            to_timestamp=messages[-1].timestamp,
        )

        record = await self._context_bank.add_record(
            project_id=payload.project_id,
            entry_type="chat_summary",
            title=f"Chat summary: {conversation.title or 'Untitled'}",
            content=summary.model_dump_json(indent=2),
            tags=["secretary", "chat-summary"],
            metadata={
                "conversation_id": payload.conversation_id,
                "message_count": len(messages),
            },
            source="chat_summarizer",
        )

        events_created: list[AgentEvent] = []

        if payload.create_action_items:
            for action_item in action_items:
                event = await self._context_bank.add_agent_event(
                    project_id=payload.project_id,
                    event=AgentEvent(
                        event_id=str(uuid.uuid4()),
                        project_id=payload.project_id,
                        source_agent="secretary_agent",
                        event_type="task_created",
                        title=f"Action item from chat: {action_item.content[:80]}",
                        description=action_item.content,
                        target_agent="pm_agent",
                        metadata={
                            "action_item_id": action_item.item_id,
                            "conversation_id": payload.conversation_id,
                            "assignee": action_item.assignee,
                            "priority": action_item.priority,
                            "source": "chat_summary",
                        },
                    ),
                )
                events_created.append(event)

        return ChatSummarizeResponse(
            summary=summary,
            context_record=record,
            events_created=events_created,
        )

    async def create_meeting(
        self,
        payload: MeetingCreateRequest,
    ) -> MeetingResponse:
        try:
            scheduled_at = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at datetime format")

        meeting = await self._chat_service.create_meeting(
            project_id=payload.project_id,
            title=payload.title,
            scheduled_at=scheduled_at,
            duration_minutes=payload.duration_minutes,
            participants=payload.participants,
        )
        return MeetingResponse(meeting=meeting)

    async def complete_meeting(
        self,
        project_id: str,
        meeting_id: str,
        payload: MeetingCompleteRequest,
    ) -> MeetingCompleteResponse:
        meeting = await self._chat_service.get_meeting(project_id, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        meeting = await self._chat_service.update_meeting(
            project_id=project_id,
            meeting_id=meeting_id,
            transcript=payload.transcript,
            status="completed",
        )

        if not meeting:
            raise HTTPException(status_code=500, detail="Failed to update meeting")

        prompt = json.dumps({
            "meeting_title": meeting.title,
            "scheduled_at": meeting.scheduled_at.isoformat(),
            "participants": meeting.participants,
            "absentees": payload.absentees,
            "transcript": payload.transcript,
            "duration_minutes": meeting.duration_minutes,
        })

        raw = await self._runtime.generate(
            "mom_generator",
            MOM_GENERATOR_INSTRUCTIONS,
            prompt,
        )

        result = self._parse_json(raw)

        action_items: list[ActionItem] = []
        for item_data in result.get("action_items", []):
            action_item = ActionItem(
                item_id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                project_id=project_id,
                content=item_data["content"],
                assignee=item_data.get("assignee"),
                due_date=datetime.fromisoformat(item_data["due_date"]) if item_data.get("due_date") else None,
                priority=item_data.get("priority", "medium"),
                source_type="meeting",
            )
            action_items.append(action_item)

        mom = MinutesOfMeeting(
            mom_id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            project_id=project_id,
            meeting_title=meeting.title,
            conducted_at=meeting.completed_at or datetime.now(timezone.utc),
            participants=meeting.participants,
            absentees=payload.absentees,
            agenda=result.get("agenda", []),
            key_discussions=result.get("key_discussions", []),
            decisions_made=result.get("decisions_made", []),
            action_items=action_items,
            next_meeting=result.get("next_meeting"),
        )

        record = await self._context_bank.add_record(
            project_id=project_id,
            entry_type="meeting_minutes",
            title=f"MoM: {meeting.title}",
            content=mom.model_dump_json(indent=2),
            tags=["secretary", "mom", "meeting"],
            metadata={
                "meeting_id": meeting_id,
                "participant_count": len(meeting.participants),
            },
            source="mom_generator",
        )

        events_created: list[AgentEvent] = []

        for action_item in action_items:
            event = await self._context_bank.add_agent_event(
                project_id=project_id,
                event=AgentEvent(
                    event_id=str(uuid.uuid4()),
                    project_id=project_id,
                    source_agent="secretary_agent",
                    event_type="task_created",
                    title=f"Action item from meeting: {action_item.content[:80]}",
                    description=action_item.content,
                    target_agent="pm_agent",
                    metadata={
                        "action_item_id": action_item.item_id,
                        "meeting_id": meeting_id,
                        "assignee": action_item.assignee,
                        "due_date": action_item.due_date.isoformat() if action_item.due_date else None,
                        "priority": action_item.priority,
                        "source": "meeting_minutes",
                    },
                ),
            )
            events_created.append(event)

        return MeetingCompleteResponse(
            meeting=meeting,
            mom=mom,
            context_record=record,
            events_created=events_created,
        )

    async def suggest_response(
        self,
        payload: SecretarySuggestRequest,
    ) -> SecretarySuggestResponse:
        conversation = await self._chat_service.get_conversation(
            payload.project_id,
            payload.conversation_id,
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = await self._chat_service.get_messages(
            project_id=payload.project_id,
            conversation_id=payload.conversation_id,
            limit=payload.context_messages,
        )

        messages.reverse()

        prompt = json.dumps({
            "conversation_context": {
                "title": conversation.title,
                "participants": conversation.participants,
                "recent_messages": [
                    {
                        "sender": m.sender_name,
                        "sender_type": m.sender_type,
                        "content": m.content,
                    }
                    for m in messages[-10:]
                ],
            },
            "current_message": payload.current_message,
            "tone": "professional but friendly",
        })

        raw = await self._runtime.generate(
            "chatbot_assistant",
            CHATBOT_ASSISTANT_INSTRUCTIONS,
            prompt,
        )

        result = self._parse_json(raw)

        return SecretarySuggestResponse(
            suggestions=result.get("suggestions", []),
            reasoning=result.get("reasoning", ""),
            tone_analysis=result.get("tone_analysis", ""),
        )

    async def list_conversations(self, project_id: str) -> list[Conversation]:
        return await self._chat_service.list_conversations(project_id)

    async def list_meetings(
        self,
        project_id: str,
        status: str | None = None,
    ) -> list[Meeting]:
        return await self._chat_service.list_meetings(project_id, status)

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
