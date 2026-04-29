from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.models.domain import (
    AgentEvent,
    ContextBankRecord,
    ProjectContextSnapshot,
    ProjectOverview,
    TimelineEntry,
)
from app.services.azure_search import AzureSearchContextBankIndex
from app.services.llm import EmbeddingService


class ContextBankService:
    def __init__(
        self,
        root_dir: Path,
        embedding_service: EmbeddingService,
        search_index: AzureSearchContextBankIndex,
    ) -> None:
        self._root_dir = Path(root_dir)
        self._embedding_service = embedding_service
        self._search_index = search_index

    @property
    def name(self) -> str:
        return self._search_index.name

    def _project_dir(self, project_id: str) -> Path:
        return self._root_dir / project_id

    def _project_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def _records_dir(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "records"

    async def bootstrap_project(self, overview: ProjectOverview) -> ProjectContextSnapshot:
        project_dir = self._project_dir(overview.project_id)
        records_dir = self._records_dir(overview.project_id)
        project_file = self._project_file(overview.project_id)

        def _write() -> None:
            records_dir.mkdir(parents=True, exist_ok=True)
            project_file.write_text(
                json.dumps(overview.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)
        return await self.get_snapshot(overview.project_id)

    async def add_record(
        self,
        project_id: str,
        entry_type: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        metadata: dict[str, object] | None = None,
        source: str | None = None,
    ) -> ContextBankRecord:
        record = ContextBankRecord(
            id=str(uuid.uuid4()),
            project_id=project_id,
            entry_type=entry_type,
            title=title,
            content=content,
            tags=tags or [],
            metadata=metadata or {},
            source=source,
            created_at=datetime.now(timezone.utc),
        )
        record_path = self._records_dir(project_id) / f"{record.id}.json"

        def _write() -> None:
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(
                json.dumps(record.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)
        embedding = await self._embedding_service.embed_text(
            f"{record.title}\n{record.content}"
        )
        await self._search_index.upsert(record, embedding)
        return record

    async def get_snapshot(self, project_id: str) -> ProjectContextSnapshot:
        overview = await self.get_project_overview(project_id)
        recent_entries = await self.list_records(project_id, limit=10)
        return ProjectContextSnapshot(
            project_id=project_id,
            overview=overview,
            recent_entries=recent_entries,
        )

    async def get_project_overview(self, project_id: str) -> ProjectOverview | None:
        project_file = self._project_file(project_id)
        if not project_file.exists():
            return None

        def _read() -> ProjectOverview:
            return ProjectOverview.model_validate_json(project_file.read_text(encoding="utf-8"))

        return await asyncio.to_thread(_read)

    async def list_records(
        self,
        project_id: str,
        limit: int = 10,
    ) -> list[ContextBankRecord]:
        records_dir = self._records_dir(project_id)
        if not records_dir.exists():
            return []

        def _read_all() -> list[ContextBankRecord]:
            items: list[ContextBankRecord] = []
            for path in records_dir.glob("*.json"):
                items.append(
                    ContextBankRecord.model_validate_json(path.read_text(encoding="utf-8"))
                )
            items.sort(key=lambda item: item.created_at, reverse=True)
            return items[:limit]

        return await asyncio.to_thread(_read_all)

    async def search_records(
        self,
        project_id: str,
        query: str,
        limit: int = 5,
    ) -> list[ContextBankRecord]:
        vector = await self._embedding_service.embed_text(query)
        indexed_results = await self._search_index.search(project_id, query, vector, top=limit)
        if indexed_results:
            return indexed_results

        records = await self.list_records(project_id, limit=100)
        lowered_terms = [term for term in query.lower().split() if term]
        if not lowered_terms:
            return records[:limit]

        scored: list[tuple[int, ContextBankRecord]] = []
        for record in records:
            haystack = " ".join(
                [
                    record.title.lower(),
                    record.content.lower(),
                    " ".join(tag.lower() for tag in record.tags),
                ]
            )
            score = sum(haystack.count(term) for term in lowered_terms)
            if score:
                scored.append((score, record))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def _timeline_file(self, project_id: str, entry_id: str) -> Path:
        return self._records_dir(project_id) / f"timeline_{entry_id}.json"

    async def add_timeline_entry(self, project_id: str, entry: TimelineEntry) -> None:
        timeline_file = self._timeline_file(project_id, entry.entry_id)

        def _write() -> None:
            timeline_file.parent.mkdir(parents=True, exist_ok=True)
            timeline_file.write_text(
                entry.model_dump_json(indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)

    async def get_timeline_entries(self, project_id: str) -> list[TimelineEntry]:
        records_dir = self._records_dir(project_id)
        if not records_dir.exists():
            return []

        def _read_all() -> list[TimelineEntry]:
            items: list[TimelineEntry] = []
            for path in records_dir.glob("timeline_*.json"):
                items.append(TimelineEntry.model_validate_json(path.read_text(encoding="utf-8")))
            items.sort(key=lambda item: (item.start_date or datetime.max.replace(tzinfo=timezone.utc)))
            return items

        return await asyncio.to_thread(_read_all)

    def _event_file(self, project_id: str, event_id: str) -> Path:
        return self._records_dir(project_id) / f"event_{event_id}.json"

    async def add_agent_event(self, project_id: str, event: AgentEvent) -> AgentEvent:
        event_file = self._event_file(project_id, event.event_id)

        def _write() -> None:
            event_file.parent.mkdir(parents=True, exist_ok=True)
            event_file.write_text(
                event.model_dump_json(indent=2),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write)

        embedding = await self._embedding_service.embed_text(f"{event.title}\n{event.description}")
        await self._search_index.upsert(
            ContextBankRecord(
                id=event.event_id,
                project_id=project_id,
                entry_type="agent_event",
                title=event.title,
                content=event.description,
                tags=["agent_event", event.event_type, event.source_agent],
                metadata=event.metadata,
                source=event.source_agent,
                created_at=event.created_at,
            ),
            embedding,
        )
        return event

    async def get_agent_events(
        self,
        project_id: str,
        target_agent: str | None = None,
        resolved: bool | None = False,
    ) -> list[AgentEvent]:
        records_dir = self._records_dir(project_id)
        if not records_dir.exists():
            return []

        def _read_all() -> list[AgentEvent]:
            items: list[AgentEvent] = []
            for path in records_dir.glob("event_*.json"):
                event = AgentEvent.model_validate_json(path.read_text(encoding="utf-8"))
                if target_agent is not None and event.target_agent != target_agent:
                    continue
                if resolved is not None and event.resolved != resolved:
                    continue
                items.append(event)
            items.sort(key=lambda item: item.created_at, reverse=True)
            return items

        return await asyncio.to_thread(_read_all)

    async def resolve_agent_event(
        self,
        project_id: str,
        event_id: str,
        resolved_by: str,
    ) -> AgentEvent | None:
        events = await self.get_agent_events(project_id, resolved=False)
        for event in events:
            if event.event_id == event_id:
                event.resolved = True
                event.resolved_at = datetime.now(timezone.utc)
                event.resolved_by = resolved_by
                event_file = self._event_file(project_id, event_id)

                def _write() -> None:
                    event_file.write_text(
                        event.model_dump_json(indent=2),
                        encoding="utf-8",
                    )

                await asyncio.to_thread(_write)
                return event
        return None
