from __future__ import annotations

import asyncio
import inspect
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
        self._tags_field_is_collection: bool | None = None

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

    @staticmethod
    def _model_parameter_names(model_cls: type[Any] | None) -> set[str]:
        if model_cls is None:
            return set()
        try:
            return set(inspect.signature(model_cls).parameters)
        except (TypeError, ValueError):
            return set()

    @staticmethod
    def _normalize_field_type(field_type: Any) -> str:
        raw_type = getattr(field_type, "value", field_type)
        return str(raw_type).replace(" ", "")

    @classmethod
    def _is_collection_string_field(cls, field: Any) -> bool:
        normalized_type = cls._normalize_field_type(getattr(field, "type", ""))
        if normalized_type in {"Collection(Edm.String)", "Collection(String)"}:
            return True
        return bool(getattr(field, "collection", False))

    def _cache_index_shape(self, index: Any) -> None:
        for field in getattr(index, "fields", []) or []:
            if getattr(field, "name", None) == "tags":
                self._tags_field_is_collection = self._is_collection_string_field(field)
                if self._tags_field_is_collection is False:
                    self._logger.warning(
                        "Azure Search index '%s' uses a legacy primitive 'tags' field; storing tags as JSON strings for compatibility.",
                        self._settings.azure_ai_search_index_name,
                    )
                return
        self._tags_field_is_collection = True

    def _serialize_tags(self, tags: list[str]) -> list[str] | str:
        if self._tags_field_is_collection is False:
            return json.dumps(tags)
        return tags

    @staticmethod
    def _deserialize_tags(raw_tags: Any) -> list[str]:
        if isinstance(raw_tags, list):
            return [str(tag) for tag in raw_tags]
        if isinstance(raw_tags, str):
            if not raw_tags.strip():
                return []
            try:
                parsed = json.loads(raw_tags)
            except json.JSONDecodeError:
                return [raw_tags]
            if isinstance(parsed, list):
                return [str(tag) for tag in parsed]
            return [raw_tags]
        return []

    def _build_vector_query(self, vector: list[float], top: int):
        if not VectorizedQuery:
            return None

        attribute_map = getattr(VectorizedQuery, "_attribute_map", {}) or {}
        parameter_names = self._model_parameter_names(VectorizedQuery)
        k_candidates: list[str] = []
        if "k" in attribute_map or "k" in parameter_names:
            k_candidates.append("k")
        if "k_nearest_neighbors" in attribute_map or "k_nearest_neighbors" in parameter_names:
            k_candidates.append("k_nearest_neighbors")
        if not k_candidates:
            k_candidates = ["k", "k_nearest_neighbors"]

        supports_kind = "kind" in attribute_map or "kind" in parameter_names
        base_kwargs: dict[str, Any] = {"vector": vector, "fields": "content_vector"}
        if supports_kind:
            base_kwargs["kind"] = "vector"

        for k_name in k_candidates:
            try:
                query = VectorizedQuery(**base_kwargs, **{k_name: top})
            except TypeError:
                continue
            if getattr(query, k_name, None) == top:
                return query

        return VectorizedQuery(**base_kwargs)

    def _build_index(self):
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="project_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="entry_type", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchableField(
                name="tags",
                type=SearchFieldDataType.String,
                collection=True,
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
        return SearchIndex(
            name=self._settings.azure_ai_search_index_name,
            fields=fields,
            vector_search=vector_search,
        )

    async def ensure_index(self) -> None:
        if self._index_ready or not self.enabled:
            return

        client = self._index_client()
        if client is None:
            self._logger.warning("Azure Search index client is not available.")
            return

        def _create_or_update() -> None:
            try:
                existing_index = client.get_index(self._settings.azure_ai_search_index_name)
                self._logger.info(
                    "Azure Search index '%s' already exists.",
                    self._settings.azure_ai_search_index_name,
                )
                self._cache_index_shape(existing_index)
                return
            except Exception as exc:
                self._logger.info(
                    "Azure Search index '%s' not found, will attempt to create: %s",
                    self._settings.azure_ai_search_index_name,
                    exc,
                )

            try:
                index_definition = self._build_index()
                self._logger.info(
                    "Creating Azure Search index '%s' with fields: %s",
                    self._settings.azure_ai_search_index_name,
                    [getattr(f, "name", None) for f in getattr(index_definition, "fields", [])],
                )
                client.create_index(index_definition)
                self._logger.info(
                    "Azure Search index '%s' created successfully.",
                    self._settings.azure_ai_search_index_name,
                )
                self._tags_field_is_collection = True
            except Exception as exc:
                self._logger.warning(
                    "Azure Search index creation failed for '%s': %s",
                    self._settings.azure_ai_search_index_name,
                    exc,
                )
                raise

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
                "tags": self._serialize_tags(record.tags),
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
                if vector:
                    vector_query = self._build_vector_query(vector, top)
                    if vector_query is not None:
                        search_kwargs["vector_queries"] = [vector_query]

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
                        tags=self._deserialize_tags(item.get("tags")),
                        metadata=json.loads(metadata_json),
                        source=item.get("source") or None,
                        created_at=item["created_at"],
                    )
                )
            return parsed
        except Exception as exc:  # pragma: no cover - network/index dependent
            self._logger.warning("Azure Search query failed: %s", exc)
            return []
