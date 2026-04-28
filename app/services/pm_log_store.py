from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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
        self._initialized = False

    @property
    def enabled(self) -> bool:
        return bool(
            CosmosClient
            and self._settings.cosmos_endpoint
            and self._settings.cosmos_key_value
            and self._settings.cosmos_database
            and self._settings.cosmos_pm_log_container
        )

    @property
    def name(self) -> str:
        return "cosmos-db" if self.enabled else "disabled"

    def _client(self):
        if not self.enabled or CosmosClient is None:
            return None
        return CosmosClient(self._settings.cosmos_endpoint, credential=self._settings.cosmos_key_value)

    async def _ensure_container(self) -> None:
        if not self.enabled or self._initialized:
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

        await asyncio.to_thread(_init)
        self._initialized = True

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
        if not self.enabled:
            return

        await self._ensure_container()
        client = self._client()
        if client is None:
            return

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

        def _write() -> None:
            database = client.get_database_client(self._settings.cosmos_database)
            container = database.get_container_client(self._settings.cosmos_pm_log_container)
            container.upsert_item(log_item)

        await asyncio.to_thread(_write)
