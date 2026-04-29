from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.models.domain import Conversation, Meeting, Message

try:
    from azure.cosmos import CosmosClient
except ImportError:  # pragma: no cover
    CosmosClient = None


class ChatService:
    def __init__(self, root_dir: Path, settings: Settings | None = None) -> None:
        self._root_dir = Path(root_dir)
        self._settings = settings
        self._initialized = False

    @property
    def _use_cosmos(self) -> bool:
        return bool(
            CosmosClient
            and self._settings
            and self._settings.cosmos_endpoint
            and self._settings.cosmos_key_value
            and self._settings.cosmos_database
            and self._settings.cosmos_chat_container
        )

    def _client(self):
        if not self._use_cosmos or CosmosClient is None or self._settings is None:
            return None
        return CosmosClient(self._settings.cosmos_endpoint, credential=self._settings.cosmos_key_value)

    async def _ensure_container(self) -> None:
        if not self._use_cosmos or self._initialized or self._settings is None:
            return

        client = self._client()
        if client is None:
            return

        def _init() -> None:
            database = client.create_database_if_not_exists(self._settings.cosmos_database)
            database.create_container_if_not_exists(
                id=self._settings.cosmos_chat_container,
                partition_key="/project_id",
            )

        await asyncio.to_thread(_init)
        self._initialized = True

    async def _upsert_document(self, document: dict[str, Any]) -> None:
        if not self._use_cosmos or self._settings is None:
            return
        await self._ensure_container()
        client = self._client()
        if client is None:
            return

        def _write() -> None:
            database = client.get_database_client(self._settings.cosmos_database)
            container = database.get_container_client(self._settings.cosmos_chat_container)
            container.upsert_item(document)

        await asyncio.to_thread(_write)

    async def _query_documents(
        self,
        *,
        project_id: str,
        item_type: str,
        extra_clause: str = "",
        extra_parameters: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if not self._use_cosmos or self._settings is None:
            return []
        await self._ensure_container()
        client = self._client()
        if client is None:
            return []

        query = "SELECT * FROM c WHERE c.project_id = @project_id AND c.item_type = @item_type"
        parameters: list[dict[str, Any]] = [
            {"name": "@project_id", "value": project_id},
            {"name": "@item_type", "value": item_type},
        ]
        if extra_clause:
            query += f" AND {extra_clause}"
        if extra_parameters:
            parameters.extend(extra_parameters)

        def _read() -> list[dict[str, Any]]:
            database = client.get_database_client(self._settings.cosmos_database)
            container = database.get_container_client(self._settings.cosmos_chat_container)
            items = container.query_items(
                query=query,
                parameters=parameters,
                partition_key=project_id,
            )
            return list(items)

        return await asyncio.to_thread(_read)

    def _chat_dir(self, project_id: str) -> Path:
        return self._root_dir / project_id / "chat"

    def _conversation_file(self, project_id: str, conversation_id: str) -> Path:
        return self._chat_dir(project_id) / f"conv_{conversation_id}.json"

    def _message_file(self, project_id: str, conversation_id: str, message_id: str) -> Path:
        return self._chat_dir(project_id) / f"msg_{conversation_id}_{message_id}.json"

    def _meeting_file(self, project_id: str, meeting_id: str) -> Path:
        return self._chat_dir(project_id) / f"meeting_{meeting_id}.json"

    async def create_conversation(
        self,
        project_id: str,
        conversation_type: str,
        title: str | None,
        participants: list[str],
    ) -> Conversation:
        conversation = Conversation(
            conversation_id=str(uuid.uuid4()),
            project_id=project_id,
            conversation_type=conversation_type,
            title=title,
            participants=participants,
        )

        if self._use_cosmos:
            await self._upsert_document(
                {
                    "id": conversation.conversation_id,
                    "project_id": project_id,
                    "item_type": "conversation",
                    **conversation.model_dump(mode="json"),
                }
            )
            return conversation

        conv_file = self._conversation_file(project_id, conversation.conversation_id)

        def _write() -> None:
            conv_file.parent.mkdir(parents=True, exist_ok=True)
            conv_file.write_text(
                conversation.model_dump_json(indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)
        return conversation

    async def get_conversation(self, project_id: str, conversation_id: str) -> Conversation | None:
        if self._use_cosmos:
            items = await self._query_documents(
                project_id=project_id,
                item_type="conversation",
                extra_clause="c.conversation_id = @conversation_id",
                extra_parameters=[{"name": "@conversation_id", "value": conversation_id}],
            )
            if not items:
                return None
            return Conversation.model_validate(items[0])

        conv_file = self._conversation_file(project_id, conversation_id)
        if not conv_file.exists():
            return None

        def _read() -> Conversation:
            return Conversation.model_validate_json(conv_file.read_text(encoding="utf-8"))

        return await asyncio.to_thread(_read)

    async def send_message(
        self,
        project_id: str,
        conversation_id: str,
        sender_type: str,
        sender_id: str,
        sender_name: str,
        content: str,
        reply_to: str | None = None,
    ) -> Message:
        message = Message(
            message_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            project_id=project_id,
            sender_type=sender_type,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            reply_to=reply_to,
        )

        if self._use_cosmos:
            await self._upsert_document(
                {
                    "id": message.message_id,
                    "project_id": project_id,
                    "item_type": "message",
                    **message.model_dump(mode="json"),
                }
            )
        else:
            msg_file = self._message_file(project_id, conversation_id, message.message_id)

            def _write() -> None:
                msg_file.parent.mkdir(parents=True, exist_ok=True)
                msg_file.write_text(
                    message.model_dump_json(indent=2),
                    encoding="utf-8",
                )

            await asyncio.to_thread(_write)

        conversation = await self.get_conversation(project_id, conversation_id)
        if conversation:
            conversation.last_message_at = message.timestamp
            await self._update_conversation(project_id, conversation)

        return message

    async def _update_conversation(self, project_id: str, conversation: Conversation) -> None:
        if self._use_cosmos:
            await self._upsert_document(
                {
                    "id": conversation.conversation_id,
                    "project_id": project_id,
                    "item_type": "conversation",
                    **conversation.model_dump(mode="json"),
                }
            )
            return

        conv_file = self._conversation_file(project_id, conversation.conversation_id)

        def _write() -> None:
            conv_file.write_text(
                conversation.model_dump_json(indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)

    async def get_messages(
        self,
        project_id: str,
        conversation_id: str,
        limit: int = 50,
        before_message_id: str | None = None,
    ) -> list[Message]:
        if self._use_cosmos:
            items = await self._query_documents(
                project_id=project_id,
                item_type="message",
                extra_clause="c.conversation_id = @conversation_id",
                extra_parameters=[{"name": "@conversation_id", "value": conversation_id}],
            )
            messages = [Message.model_validate(item) for item in items]
            messages.sort(key=lambda m: m.timestamp, reverse=True)
            if before_message_id:
                try:
                    before_idx = next(i for i, m in enumerate(messages) if m.message_id == before_message_id)
                    messages = messages[before_idx + 1:]
                except StopIteration:
                    pass
            return messages[:limit]

        chat_dir = self._chat_dir(project_id)
        if not chat_dir.exists():
            return []

        def _read_all() -> list[Message]:
            items: list[Message] = []
            pattern = f"msg_{conversation_id}_*.json"
            for path in chat_dir.glob(pattern):
                items.append(Message.model_validate_json(path.read_text(encoding="utf-8")))
            items.sort(key=lambda m: m.timestamp, reverse=True)

            if before_message_id:
                try:
                    before_idx = next(i for i, m in enumerate(items) if m.message_id == before_message_id)
                    items = items[before_idx + 1:]
                except StopIteration:
                    pass

            return items[:limit]

        return await asyncio.to_thread(_read_all)

    async def create_meeting(
        self,
        project_id: str,
        title: str,
        scheduled_at: datetime,
        duration_minutes: int,
        participants: list[str],
    ) -> Meeting:
        meeting = Meeting(
            meeting_id=str(uuid.uuid4()),
            project_id=project_id,
            title=title,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            participants=participants,
        )

        if self._use_cosmos:
            await self._upsert_document(
                {
                    "id": meeting.meeting_id,
                    "project_id": project_id,
                    "item_type": "meeting",
                    **meeting.model_dump(mode="json"),
                }
            )
            return meeting

        meeting_file = self._meeting_file(project_id, meeting.meeting_id)

        def _write() -> None:
            meeting_file.parent.mkdir(parents=True, exist_ok=True)
            meeting_file.write_text(
                meeting.model_dump_json(indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)
        return meeting

    async def get_meeting(self, project_id: str, meeting_id: str) -> Meeting | None:
        if self._use_cosmos:
            items = await self._query_documents(
                project_id=project_id,
                item_type="meeting",
                extra_clause="c.meeting_id = @meeting_id",
                extra_parameters=[{"name": "@meeting_id", "value": meeting_id}],
            )
            if not items:
                return None
            return Meeting.model_validate(items[0])

        meeting_file = self._meeting_file(project_id, meeting_id)
        if not meeting_file.exists():
            return None

        def _read() -> Meeting:
            return Meeting.model_validate_json(meeting_file.read_text(encoding="utf-8"))

        return await asyncio.to_thread(_read)

    async def update_meeting(
        self,
        project_id: str,
        meeting_id: str,
        transcript: str | None = None,
        status: str | None = None,
    ) -> Meeting | None:
        meeting = await self.get_meeting(project_id, meeting_id)
        if not meeting:
            return None

        if transcript is not None:
            meeting.transcript = transcript
        if status is not None:
            meeting.status = status
            if status == "completed":
                meeting.completed_at = datetime.now(timezone.utc)

        if self._use_cosmos:
            await self._upsert_document(
                {
                    "id": meeting.meeting_id,
                    "project_id": project_id,
                    "item_type": "meeting",
                    **meeting.model_dump(mode="json"),
                }
            )
            return meeting

        meeting_file = self._meeting_file(project_id, meeting_id)

        def _write() -> None:
            meeting_file.write_text(
                meeting.model_dump_json(indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)
        return meeting

    async def list_conversations(self, project_id: str) -> list[Conversation]:
        if self._use_cosmos:
            items = await self._query_documents(project_id=project_id, item_type="conversation")
            conversations = [Conversation.model_validate(item) for item in items]
            conversations.sort(key=lambda c: c.last_message_at or c.created_at, reverse=True)
            return conversations

        chat_dir = self._chat_dir(project_id)
        if not chat_dir.exists():
            return []

        def _read_all() -> list[Conversation]:
            items: list[Conversation] = []
            for path in chat_dir.glob("conv_*.json"):
                items.append(Conversation.model_validate_json(path.read_text(encoding="utf-8")))
            items.sort(key=lambda c: c.last_message_at or c.created_at, reverse=True)
            return items

        return await asyncio.to_thread(_read_all)

    async def list_meetings(
        self,
        project_id: str,
        status: str | None = None,
    ) -> list[Meeting]:
        if self._use_cosmos:
            items = await self._query_documents(project_id=project_id, item_type="meeting")
            meetings = [Meeting.model_validate(item) for item in items]
            if status is not None:
                meetings = [meeting for meeting in meetings if meeting.status == status]
            meetings.sort(key=lambda m: m.scheduled_at, reverse=True)
            return meetings

        chat_dir = self._chat_dir(project_id)
        if not chat_dir.exists():
            return []

        def _read_all() -> list[Meeting]:
            items: list[Meeting] = []
            for path in chat_dir.glob("meeting_*.json"):
                meeting = Meeting.model_validate_json(path.read_text(encoding="utf-8"))
                if status is None or meeting.status == status:
                    items.append(meeting)
            items.sort(key=lambda m: m.scheduled_at, reverse=True)
            return items

        return await asyncio.to_thread(_read_all)
