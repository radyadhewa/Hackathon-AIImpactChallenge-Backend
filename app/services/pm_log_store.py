from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings

try:
    from azure.cosmos import CosmosClient
    from azure.cosmos.exceptions import CosmosResourceExistsError
except ImportError:  # pragma: no cover
    CosmosClient = None
    CosmosResourceExistsError = None


class PmLogStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root_dir = Path(settings.context_bank_dir)
        self._initialized = False

    @property
    def _use_cosmos(self) -> bool:
        return bool(
            CosmosClient
            and self._settings.cosmos_endpoint
            and self._settings.cosmos_key_value
            and self._settings.cosmos_database
            and self._settings.cosmos_pm_log_container
        )

    @property
    def name(self) -> str:
        return "cosmos-db" if self._use_cosmos else "local-json"

    def _client(self):
        if not self._use_cosmos or CosmosClient is None:
            return None
        return CosmosClient(self._settings.cosmos_endpoint, credential=self._settings.cosmos_key_value)

    def _logs_dir(self, project_id: str) -> Path:
        return self._root_dir / project_id / "pm_logs"

    def _log_file(self, project_id: str, log_id: str) -> Path:
        safe_log_id = log_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        return self._logs_dir(project_id) / f"{safe_log_id}.json"

    async def _ensure_container(self) -> None:
        if not self._use_cosmos or self._initialized:
            return

        client = self._client()
        if client is None:
            return

        def _init() -> None:
            database = client.create_database_if_not_exists(self._settings.cosmos_database)
            try:
                database.create_container_if_not_exists(
                    id=self._settings.cosmos_pm_log_container,
                    partition_key="/project_id",
                )
            except CosmosResourceExistsError:
                pass

        try:
            await asyncio.to_thread(_init)
            self._initialized = True
        except Exception:
            return

    async def log_action(
        self,
        *,
        project_id: str,
        action_type: str,
        summary: str,
        payload: dict[str, Any],
        actor: str = "pm_agent",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        log_item = {
            "id": f"{project_id}:{action_type}:{datetime.now(timezone.utc).isoformat()}",
            "project_id": project_id,
            "action_type": action_type,
            "summary": summary,
            "payload": payload,
            "actor": actor,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if self._use_cosmos:
            try:
                await self._ensure_container()
                client = self._client()
                if client is None:
                    return

                def _write() -> None:
                    database = client.get_database_client(self._settings.cosmos_database)
                    container = database.get_container_client(self._settings.cosmos_pm_log_container)
                    container.upsert_item(log_item)

                await asyncio.to_thread(_write)
                return
            except Exception:
                return

        log_file = self._log_file(project_id, log_item["id"])

        def _write_local() -> None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text(json.dumps(log_item, indent=2), encoding="utf-8")

        await asyncio.to_thread(_write_local)

    async def list_logs(
        self,
        *,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
        action_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._use_cosmos:
            try:
                client = self._client()
                if client is None:
                    return []

                query = "SELECT * FROM c WHERE c.project_id = @project_id"
                parameters = [{"name": "@project_id", "value": project_id}]
                if action_type:
                    query += " AND c.action_type = @action_type"
                    parameters.append({"name": "@action_type", "value": action_type})
                query += " ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit"
                parameters.append({"name": "@offset", "value": offset})
                parameters.append({"name": "@limit", "value": limit})

                def _query() -> list[dict[str, Any]]:
                    database = client.get_database_client(self._settings.cosmos_database)
                    container = database.get_container_client(self._settings.cosmos_pm_log_container)
                    items = container.query_items(
                        query=query,
                        parameters=parameters,
                        enable_cross_partition_query=True,
                    )
                    return list(items)

                return await asyncio.to_thread(_query)
            except Exception:
                return []

        logs_dir = self._logs_dir(project_id)
        if not logs_dir.exists():
            return []

        def _read_local() -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
            for path in logs_dir.glob("*.json"):
                items.append(json.loads(path.read_text(encoding="utf-8")))

            if action_type:
                items = [item for item in items if item.get("action_type") == action_type]

            items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
            return items[offset : offset + limit]

        return await asyncio.to_thread(_read_local)
