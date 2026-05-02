from types import SimpleNamespace

from app.core.config import Settings
from app.services import azure_search
from app.services.azure_search import AzureSearchContextBankIndex


def test_build_index_defines_tags_as_string_collection(monkeypatch) -> None:
    class FakeSearchFieldDataType:
        String = "Edm.String"
        DateTimeOffset = "Edm.DateTimeOffset"
        Single = "Edm.Single"

        @staticmethod
        def Collection(value: str) -> str:
            return f"Collection({value})"

    monkeypatch.setattr(azure_search, "SearchFieldDataType", FakeSearchFieldDataType)
    monkeypatch.setattr(
        azure_search,
        "SimpleField",
        lambda **kwargs: SimpleNamespace(field_kind="simple", **kwargs),
    )
    monkeypatch.setattr(
        azure_search,
        "SearchableField",
        lambda **kwargs: SimpleNamespace(field_kind="searchable", **kwargs),
    )
    monkeypatch.setattr(
        azure_search,
        "SearchField",
        lambda **kwargs: SimpleNamespace(field_kind="field", **kwargs),
    )
    monkeypatch.setattr(
        azure_search,
        "VectorSearch",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        azure_search,
        "VectorSearchProfile",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        azure_search,
        "HnswAlgorithmConfiguration",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        azure_search,
        "SearchIndex",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    index = AzureSearchContextBankIndex(Settings())
    built_index = index._build_index()
    tags_field = next(field for field in built_index.fields if field.name == "tags")

    assert tags_field.type == FakeSearchFieldDataType.String
    assert tags_field.collection is True


def test_cache_index_shape_handles_legacy_primitive_tags() -> None:
    index = AzureSearchContextBankIndex(Settings())
    legacy_index = SimpleNamespace(
        fields=[SimpleNamespace(name="tags", type="Edm.String", collection=False)]
    )

    index._cache_index_shape(legacy_index)
    serialized = index._serialize_tags(["pm", "planning"])

    assert index._tags_field_is_collection is False
    assert serialized == '["pm", "planning"]'
    assert index._deserialize_tags(serialized) == ["pm", "planning"]


def test_build_vector_query_uses_k_for_newer_sdk(monkeypatch) -> None:
    class FakeVectorizedQuery:
        _attribute_map = {"vector": {}, "fields": {}, "k": {}}

        def __init__(self, **kwargs) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    monkeypatch.setattr(azure_search, "VectorizedQuery", FakeVectorizedQuery)

    index = AzureSearchContextBankIndex(Settings())
    query = index._build_vector_query([0.1, 0.2], top=4)

    assert query is not None
    assert query.k == 4
    assert query.fields == "content_vector"
    assert not hasattr(query, "k_nearest_neighbors")


def test_build_vector_query_falls_back_to_k_nearest_neighbors(monkeypatch) -> None:
    class FakeVectorizedQuery:
        _attribute_map = {"vector": {}, "fields": {}, "k_nearest_neighbors": {}}

        def __init__(self, **kwargs) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    monkeypatch.setattr(azure_search, "VectorizedQuery", FakeVectorizedQuery)

    index = AzureSearchContextBankIndex(Settings())
    query = index._build_vector_query([0.1, 0.2], top=6)

    assert query is not None
    assert query.k_nearest_neighbors == 6
    assert query.fields == "content_vector"
    assert not hasattr(query, "k")
