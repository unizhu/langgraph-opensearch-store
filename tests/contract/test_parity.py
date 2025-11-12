import importlib
import os
from collections.abc import Iterator
from typing import Any, Iterable, Protocol, cast

import pytest

from langgraph_opensearch_store.store import OpenSearchStore
from langgraph.store.memory import InMemoryStore


class _PostgresStoreProto(Protocol):
    @classmethod
    def from_conn_string(cls, dsn: str) -> "_PostgresStoreProto":
        ...

    def setup(self) -> None:
        ...

    def put(self, namespace, key, value) -> None:
        ...

    def delete(self, namespace, key) -> None:
        ...

    def get(self, namespace, key) -> Any:
        ...

    def search(self, namespace_prefix, *, query: str | None, limit: int) -> Any:
        ...

    def list_namespaces(self, prefix) -> Any:
        ...

    def get_stats(self) -> Any:
        ...

class _MemoryReferenceStore(_PostgresStoreProto):
    def __init__(self) -> None:
        self._store = InMemoryStore()

    @classmethod
    def from_conn_string(cls, dsn: str) -> "_MemoryReferenceStore":
        return cls()

    def setup(self) -> None:  # pragma: no cover - nothing to do
        return None

    def put(self, namespace, key, value) -> None:
        self._store.put(namespace, key, value)

    def delete(self, namespace, key) -> None:
        self._store.delete(namespace, key)

    def get(self, namespace, key):
        return self._store.get(namespace, key)

    def search(self, namespace_prefix, *, query: str | None, limit: int):
        return self._store.search(namespace_prefix, query=query, limit=limit)

    def list_namespaces(self, prefix):
        return self._store.list_namespaces(prefix=prefix)

    def get_stats(self):
        total = sum(len(items) for items in self._store._data.values())  # type: ignore[attr-defined]
        return {"total_items": total}


def _load_postgres_store() -> tuple[type[_PostgresStoreProto], str]:
    try:
        module = importlib.import_module("langgraph.store.postgres")
    except ModuleNotFoundError:
        return _MemoryReferenceStore, "memory"
    pg_cls = cast(type[_PostgresStoreProto], getattr(module, "PostgresStore", None))
    if pg_cls is None:
        return _MemoryReferenceStore, "memory"
    return pg_cls, "postgres"


ReferenceStore, REFERENCE_IMPL = _load_postgres_store()

DATASET = [
    (("prefs", "user_a"), "color", {"text": "I like blue"}),
    (("prefs", "user_a"), "food", {"text": "I like pizza"}),
    (("prefs", "user_b"), "color", {"text": "I like red"}),
]

pytestmark = pytest.mark.contract


def _require_env() -> tuple[str, str]:
    os_conn = os.getenv("OPENSEARCH_CONN")
    missing: list[str] = []
    pg_dsn: str | None
    if REFERENCE_IMPL == "postgres":
        pg_dsn = os.getenv("POSTGRES_DSN")
        if not pg_dsn:
            missing.append("POSTGRES_DSN")
    else:
        pg_dsn = "memory://local"
    if not os_conn:
        missing.append("OPENSEARCH_CONN")
    if missing:
        pytest.skip("Set " + " and ".join(missing) + " to run contract tests")
    assert pg_dsn is not None
    assert os_conn is not None
    return pg_dsn, os_conn


@pytest.fixture()
def reference_store() -> Iterator[_PostgresStoreProto]:
    pg_dsn, _ = _require_env()
    store: _PostgresStoreProto = ReferenceStore.from_conn_string(pg_dsn)
    store.setup()
    _load_dataset(store)
    yield store
    if REFERENCE_IMPL == "postgres":
        _truncate_store(store)


@pytest.fixture()
def opensearch_store():
    _, os_conn = _require_env()
    store = OpenSearchStore.from_conn_string(os_conn)
    store.setup()
    _load_dataset(store)
    yield store


def _load_dataset(store: _PostgresStoreProto | OpenSearchStore) -> None:
    for namespace, key, doc in DATASET:
        store.put(namespace, key, doc)


def _truncate_store(store: _PostgresStoreProto) -> None:
    for namespace, key, _ in DATASET:
        store.delete(namespace, key)


def _sorted(items: Iterable):
    return sorted(items, key=lambda item: (tuple(item.namespace), item.key))


def test_parity_get(reference_store, opensearch_store):
    for namespace, key, _ in DATASET:
        ref = reference_store.get(namespace, key)
        ours = opensearch_store.get(namespace, key)
        assert ref.value == ours.value


def test_parity_search(reference_store, opensearch_store):
    ref_results = reference_store.search(("prefs",), query="like", limit=10)
    os_results = opensearch_store.search(("prefs",), query="like", limit=10)
    assert len(ref_results) == len(os_results)


def test_parity_list_namespaces(reference_store, opensearch_store):
    ref_list = reference_store.list_namespaces(prefix=("prefs",))
    os_list = opensearch_store.list_namespaces(prefix=("prefs",))
    assert set(ref_list) == set(os_list)


def test_parity_stats(reference_store, opensearch_store):
    ref_stats = reference_store.get_stats()
    os_stats = opensearch_store.get_stats()
    assert ref_stats["total_items"] == os_stats["total_items"]
