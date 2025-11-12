"""Operational CLI for LangGraph OpenSearch Store."""

from __future__ import annotations

import json
from typing import Any

import click

from .store import OpenSearchStore


def _comma_to_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [segment.strip() for segment in value.split(",") if segment.strip()]
    return items or None


@click.group()
@click.option("--conn", "conn_str", envvar="OPENSEARCH_CONN", help="Connection string.")
@click.option("--hosts", default=None, envvar="OPENSEARCH_HOSTS")
@click.option("--auth-mode", default=None, envvar="OPENSEARCH_AUTH_MODE")
@click.option("--username", default=None, envvar="OPENSEARCH_USERNAME")
@click.option("--password", default=None, envvar="OPENSEARCH_PASSWORD")
@click.pass_context
def cli(ctx: click.Context, conn_str: str | None, **kwargs: Any) -> None:
    params = {k: v for k, v in kwargs.items() if v is not None}
    if conn_str:
        store = OpenSearchStore.from_conn_string(conn_str, **params)
    else:
        store = OpenSearchStore.from_params(**params)
    store.setup()
    ctx.obj = store


@cli.command()
@click.pass_obj
def health(store: OpenSearchStore) -> None:
    click.echo(json.dumps(store.get_health(), indent=2))


@cli.command()
@click.pass_obj
def stats(store: OpenSearchStore) -> None:
    click.echo(json.dumps(store.get_stats(), indent=2))


@cli.command(name="ttl-sweep")
@click.option("--batch-size", default=1000, type=int)
@click.pass_obj
def ttl_sweep(store: OpenSearchStore, batch_size: int) -> None:
    result = store.ttl_manager.run_once(batch_size=batch_size)
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.option("--rollover/--no-rollover", default=False, help="Trigger an alias rollover after installing templates.")
@click.option("--new-index", default=None, help="Optional name for the new backing index.")
@click.pass_obj
def migrate(store: OpenSearchStore, rollover: bool, new_index: str | None) -> None:
    result = store.migrate(rollover=rollover, new_index=new_index)
    click.echo(json.dumps(result, indent=2))


@cli.group()
@click.pass_context
def snapshots(ctx: click.Context) -> None:
    """Snapshot operations wrapper."""


@snapshots.command("create")
@click.option("--repository", required=True)
@click.option("--snapshot", required=True)
@click.option("--indices", default=None, help="Comma-separated list of indices to include.")
@click.option("--wait/--no-wait", default=True)
@click.pass_obj
def snapshots_create(
    store: OpenSearchStore,
    repository: str,
    snapshot: str,
    indices: str | None,
    wait: bool,
) -> None:
    result = store.create_snapshot(
        repository=repository,
        snapshot=snapshot,
        indices=_comma_to_list(indices),
        wait=wait,
    )
    click.echo(json.dumps(result, indent=2))


@snapshots.command("restore")
@click.option("--repository", required=True)
@click.option("--snapshot", required=True)
@click.option("--indices", default=None, help="Comma-separated list of indices to restore.")
@click.option("--wait/--no-wait", default=True)
@click.pass_obj
def snapshots_restore(
    store: OpenSearchStore,
    repository: str,
    snapshot: str,
    indices: str | None,
    wait: bool,
) -> None:
    result = store.restore_snapshot(
        repository=repository,
        snapshot=snapshot,
        indices=_comma_to_list(indices),
        wait=wait,
    )
    click.echo(json.dumps(result, indent=2))


@snapshots.command("delete")
@click.option("--repository", required=True)
@click.option("--snapshot", required=True)
@click.pass_obj
def snapshots_delete(store: OpenSearchStore, repository: str, snapshot: str) -> None:
    result = store.delete_snapshot(repository=repository, snapshot=snapshot)
    click.echo(json.dumps(result, indent=2))


def main() -> None:  # pragma: no cover - CLI entrypoint
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
