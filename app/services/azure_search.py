from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.core.config import Settings
from app.models.domain import ContextBankRecord

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import DefaultAzureCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SearchableField,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )
    from azure.search.documents.models import VectorizedQuery
except ImportError:  # pragma: no cover
    AzureKeyCredential = None
    DefaultAzureCredential = None
    SearchClient = None
    SearchIndexClient = None
    SearchField = None
    SearchFieldDataType = None
    SearchIndex = None
    SearchableField = None
    SimpleField = None
    HnswAlgorithmConfiguration = None
    VectorSearch = None
    VectorSearchProfile = None
    VectorizedQuery = None


class AzureSearchContextBankIndex:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._index_ready = False
        self._logger = logging.getLogger(__name__)

    @property
    def enabled(self) -> bool:
        return bool(
            SearchClient
            and self._settings.azure_ai_search_endpoint
            and (
                self._settings.azure_ai_search_api_key_value
                or self._settings.azure_use_default_credential
            )
        )

    @property
    def name(self) -> str:
        return "azure-ai-search" if self.enabled else "local-json-only"

    def _credential(self):
        if self._settings.azure_ai_search_api_key_value and AzureKeyCredential:
            return AzureKeyCredential(self._settings.azure_ai_search_api_key_value)
        if self._settings.azure_use_default_credential and DefaultAzureCredential:
            return DefaultAzureCredential()
        return None

    def _index_client(self):
        credential = self._credential()
        if not self.enabled or credential is None or SearchIndexClient is None:
            return None
        return SearchIndexClient(
            endpoint=self._settings.azure_ai_search_endpoint,
            credential=credential,
        )

    def _search_client(self):
        credential = self._credential()
        if not self.enabled or credential is None or SearchClient is None:
            return None
        return SearchClient(
            endpoint=self._settings.azure_ai_search_endpoint,
            index_name=self._settings.azure_ai_search_index_name,
            credential=credential,
        )

    async def ensure_index(self) -> None:
        if self._index_ready or not self.enabled:
            return

        client = self._index_client()
        if client is None:
            return

        def _create_or_update() -> None:
            try:
                client.get_index(self._settings.azure_ai_search_index_name)
                return
            except Exception:
                pass

            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SimpleField(name="project_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="entry_type", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="title", type=SearchFieldDataType.String),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SearchableField(
                    name="tags",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                ),
                SearchableField(name="source", type=SearchFieldDataType.String),
                SearchableField(name="metadata_json", type=SearchFieldDataType.String),
                SimpleField(
                    name="created_at",
                    type=SearchFieldDataType.DateTimeOffset,
                    sortable=True,
                    filterable=True,
                ),
                SearchField(
                    name="content_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=self._settings.azure_ai_search_vector_dimensions,
                    vector_search_profile_name="content-vector-profile",
                ),
            ]

            vector_search = VectorSearch(
                algorithms=[HnswAlgorithmConfiguration(name="content-hnsw")],
                profiles=[
                    VectorSearchProfile(
                        name="content-vector-profile",
                        algorithm_configuration_name="content-hnsw",
                    )
                ],
            )
            index = SearchIndex(
                name=self._settings.azure_ai_search_index_name,
                fields=fields,
                vector_search=vector_search,
            )
            client.create_index(index)

        await asyncio.to_thread(_create_or_update)
        self._index_ready = True

    async def upsert(self, record: ContextBankRecord, vector: list[float] | None) -> None:
        if not self.enabled:
            return

        try:
            await self.ensure_index()
            client = self._search_client()
            if client is None:
                return

            document = {
                "id": record.id,
                "project_id": record.project_id,
                "entry_type": record.entry_type,
                "title": record.title,
                "content": record.content,
                "tags": record.tags,
                "source": record.source or "",
                "metadata_json": json.dumps(record.metadata),
                "created_at": record.created_at.isoformat(),
            }
            if vector:
                document["content_vector"] = vector

            await asyncio.to_thread(client.upload_documents, [document])
        except Exception as exc:  # pragma: no cover - network/index dependent
            self._logger.warning("Azure Search upsert failed: %s", exc)
            return

    async def search(
        self,
        project_id: str,
        query_text: str,
        vector: list[float] | None,
        top: int = 5,
    ) -> list[ContextBankRecord]:
        if not self.enabled:
            return []

        try:
            await self.ensure_index()
            client = self._search_client()
            if client is None:
                return []

            def _run_search() -> list[dict[str, Any]]:
                search_kwargs: dict[str, Any] = {
                    "search_text": query_text or "*",
                    "filter": f"project_id eq '{project_id}'",
                    "top": top,
                }
                if vector and VectorizedQuery:
                    search_kwargs["vector_queries"] = [
                        VectorizedQuery(
                            vector=vector,
                            k_nearest_neighbors=top,
                            fields="content_vector",
                        )
                    ]

                return list(client.search(**search_kwargs))

            raw_results = await asyncio.to_thread(_run_search)
            parsed: list[ContextBankRecord] = []
            for item in raw_results:
                metadata_json = item.get("metadata_json") or "{}"
                parsed.append(
                    ContextBankRecord(
                        id=item["id"],
                        project_id=item["project_id"],
                        entry_type=item["entry_type"],
                        title=item["title"],
                        content=item["content"],
                        tags=item.get("tags") or [],
                        metadata=json.loads(metadata_json),
                        source=item.get("source") or None,
                        created_at=item["created_at"],
                    )
                )
            return parsed
        except Exception as exc:  # pragma: no cover - network/index dependent
            self._logger.warning("Azure Search query failed: %s", exc)
            return []
