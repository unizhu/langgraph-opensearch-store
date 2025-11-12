from unittest.mock import MagicMock

from langgraph_opensearch_store.config import Settings
from langgraph_opensearch_store.schema import TemplateManager


def test_template_manager_apply_creates_indices():
    client = MagicMock()
    client.indices = MagicMock()
    client.indices.exists.return_value = False

    settings = Settings(hosts="http://localhost:9200")
    manager = TemplateManager(client, settings)
    manager.apply()

    assert client.indices.put_index_template.called
    created_indices = [call.kwargs["index"] for call in client.indices.create.call_args_list]
    assert settings.data_index_bootstrap in created_indices
    assert settings.namespace_index_name in created_indices
    client.indices.put_alias.assert_called_with(
        index=settings.data_index_bootstrap,
        name=settings.data_index_alias,
        ignore=[404],
    )


def test_template_manager_upgrade_rollover():
    client = MagicMock()
    client.indices = MagicMock()
    client.indices.exists.return_value = True
    client.indices.rollover.return_value = {"rolled_over": True, "new_index": "custom"}

    settings = Settings(hosts="http://localhost:9200")
    manager = TemplateManager(client, settings)

    result = manager.upgrade(rollover=True, new_index="custom")

    client.indices.rollover.assert_called_with(
        alias=settings.data_index_alias,
        new_index="custom",
        body={"conditions": {"max_docs": 0}},
        dry_run=False,
        ignore=[400],
    )
    assert result == {"rolled_over": True, "new_index": "custom"}


def test_template_manager_upgrade_without_rollover():
    client = MagicMock()
    client.indices = MagicMock()
    client.indices.exists.return_value = True

    settings = Settings(hosts="http://localhost:9200")
    manager = TemplateManager(client, settings)

    result = manager.upgrade(rollover=False)

    client.indices.rollover.assert_not_called()
    assert result == {"rolled_over": False, "new_index": None}
