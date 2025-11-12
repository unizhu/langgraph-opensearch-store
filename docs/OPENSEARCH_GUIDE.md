# LangGraph OpenSearch Store — Ops Guide

## Template & Index Lifecycle
- Run `uv run python -m langgraph_opensearch_store.cli health` after provisioning to verify the data alias (`<prefix>-data`) and namespace index exist.
- Use `langgraph-opensearch migrate --rollover` to reapply templates and roll the alias to a fresh backing index after bumping `Settings.template_version`. Pass `--new-index` to control the destination name.
- Manual workflow remains supported:
  1. Bump `Settings.template_version` and release.
  2. Run `langgraph-opensearch migrate --no-rollover` if you only need the template update.
  3. Reindex/rollover as needed, then retire obsolete indices.

## ILM & TTL
- Data index stores documents plus `ttl_expires_at`. Set `OPENSEARCH_TTL_MINUTES_DEFAULT` for default expiration.
- Enable refresh-on-read via `OPENSEARCH_TTL_REFRESH_ON_READ=true` if you need session-style behavior.
- Use `langgraph-opensearch ttl-sweep --batch-size 1000` to delete expired docs on demand or wire it into cron.

## CLI Cheatsheet

`$OPENSEARCH_CONN` looks like `https://user:pass@host:9200/?search_mode=hybrid&ttl_minutes=1440`.

```
langgraph-opensearch --conn $OPENSEARCH_CONN health
langgraph-opensearch --conn $OPENSEARCH_CONN stats
langgraph-opensearch --conn $OPENSEARCH_CONN ttl-sweep --batch-size 500
langgraph-opensearch --conn $OPENSEARCH_CONN migrate --rollover
langgraph-opensearch --conn $OPENSEARCH_CONN snapshots create --repository langgraph --snapshot nightly --indices langgraph-data-*
langgraph-opensearch --conn $OPENSEARCH_CONN snapshots restore --repository langgraph --snapshot nightly --indices langgraph-data-*
```

## Snapshots & Disaster Recovery
- Create a snapshot: `langgraph-opensearch snapshots create --repository <repo> --snapshot <name> [--indices data1,data2] [--no-wait]`
- Restore selectively: `langgraph-opensearch snapshots restore --repository <repo> --snapshot <name> --indices langgraph-data-*`
- Clean up old backups with `langgraph-opensearch snapshots delete --repository <repo> --snapshot <name>`.
- Repositories are configured directly in OpenSearch (S3, FS, etc.); the CLI simply wraps `snapshot.create/restore/delete` for day-two ops.

## Metrics & Logging
- `OPENSEARCH_LOG_OPERATIONS=false` silences request-level logs.
- `OPENSEARCH_METRICS_ENABLED=true` emits JSON metrics under `langgraph.opensearch.store.metrics` (hook your log forwarder into Prometheus/Otel).
- TTL sweeps log `event=ttl_sweep` with deleted counts + duration.

## AWS SigV4 Notes
- Set `OPENSEARCH_AUTH_MODE=sigv4`, `AWS_REGION`, and optionally `AWS_ROLE_ARN`.
- For web identity (IRSA), set `AWS_WEB_IDENTITY_TOKEN_FILE` — the client will call `AssumeRoleWithWebIdentity` before signing requests.
- Retries/backoff are enabled for 429/5xx by default; override via `OPENSEARCH_MAX_RETRIES` in future if needed.

## Troubleshooting
| Symptom | Check | Fix |
| --- | --- | --- |
| `security_exception` on startup | IAM role lacks `es:ESHttp*` | Update domain access policy + role mapping |
| `ttl_sweep` deletes zero docs | Ensure docs have `ttl_expires_at` and `OPENSEARCH_TTL_MINUTES_DEFAULT` is set | Re-ingest or set default TTL |
| High query latency | Review `search_mode` (`hybrid` costs more) and tune `search_num_candidates` | Lower `num_candidates` or use text-only |
| SigV4 auth fails | Confirm `AWS_ROLE_ARN` + `AWS_WEB_IDENTITY_TOKEN_FILE` | Recreate credentials / update env |

## Contract Tests
- Run `uv run pytest tests/contract -m contract` locally (requires Postgres + OpenSearch endpoints).
- Trigger the `contract-tests` GitHub Action (manual dispatch) to spin up dockerized services and execute the suite in CI.
