# Multi-Tenancy & Query Safety

CyberSentinel enforces **mandatory tenant isolation** across both data stores
(ClickHouse and Neo4j). Every read, write, and query is automatically scoped
to a `tenant_id`, preventing cross-tenant data leakage.

## Architecture Decision

**Approach chosen: tenant_id property on every node/row**

Rather than per-tenant Neo4j databases or separate ClickHouse databases, we
stamp a `tenant_id` on every piece of data:

| Concern | Approach |
|---|---|
| Neo4j isolation | `tenant_id` property on every node; all MATCH/MERGE include `tenant_id` filter |
| ClickHouse isolation | `tenant_id` column in every table; partition key in ORDER BY |
| Query safety | `SafeQueryBuilder` with injection-pattern detection |
| Enforcement | Immutable `tenant_id` set at client construction time |

**Why not per-tenant databases?**
- Neo4j Community Edition only supports a single database.
- Per-tenant databases add operational complexity (provisioning, migrations,
  connection routing) that is unnecessary for a lab/mid-scale deployment.
- Property-level isolation is auditable — every query can be inspected for
  tenant scoping.

## Neo4j Tenant Isolation

### Client construction

```python
from storage import Neo4jClient

# tenant_id is mandatory and immutable
client = Neo4jClient(tenant_id="acme")
client.connect()
```

### How it works

Every method on `Neo4jClient` injects `tenant_id` into Cypher:

- **MERGE** operations include `tenant_id` in the match key, so nodes are
  unique per tenant.
- **MATCH** operations filter on `tenant_id`, preventing cross-tenant reads.
- The `entity_type` parameter in `create_ttp_indication` is validated against
  a whitelist (`_VALID_ENTITY_TYPES`) to prevent Cypher injection via label
  formatting.

### Schema indexes

`schema.cql` includes `tenant_id` indexes on all 12 node types for query
performance:

```cypher
CREATE INDEX host_tenant_idx IF NOT EXISTS FOR (h:Host) ON (h.tenant_id);
CREATE INDEX ttp_tenant_idx  IF NOT EXISTS FOR (t:TTP)  ON (t.tenant_id);
-- ... (all entity types)
```

### GraphSynchronizer

`GraphSynchronizer` and `KnowledgeGraphManager` inherit the tenant from the
`Neo4jClient` passed at construction:

```python
from knowledge.graph_sync import GraphSynchronizer

sync = GraphSynchronizer(neo4j_client)  # uses neo4j_client.tenant_id
sync.sync_attack_to_graph(documents)
```

## ClickHouse Tenant Isolation

### Client construction

```python
from storage import ClickHouseClient

ch = ClickHouseClient(tenant_id="acme")
ch.connect()
```

### How it works

- **Inserts** always include `tenant_id` as the second column in every row.
- **Queries** use `SafeQueryBuilder`, which automatically prepends
  `WHERE tenant_id = %(tenant_id)s` to every query.

### DDL

All five tables include `tenant_id` as part of the `ORDER BY` key:

```sql
CREATE TABLE IF NOT EXISTS telemetry (
  ts DateTime64(3),
  tenant_id LowCardinality(String),
  host String,
  ...
) ENGINE = MergeTree ORDER BY (tenant_id, ts, host);
```

## SafeQueryBuilder

`SafeQueryBuilder` is a fluent query builder that enforces two invariants:

1. **Tenant filter always present** — the first WHERE clause is always
   `tenant_id = %(tenant_id)s`.
2. **Injection patterns rejected** — table names, column expressions, WHERE
   clauses, and parameter values are scanned for common SQL injection patterns.

### Usage

```python
from storage.clickhouse.client import SafeQueryBuilder

qb = (
    SafeQueryBuilder("telemetry", tenant_id="acme")
    .columns("ts", "host", "source")
    .where("host = %(host)s", host="web-01")
    .order_by("ts DESC")
    .limit(100)
)

sql, params = qb.build()
# sql:    SELECT ts, host, source FROM telemetry
#         WHERE tenant_id = %(tenant_id)s AND host = %(host)s
#         ORDER BY ts DESC LIMIT 100
# params: {"tenant_id": "acme", "host": "web-01"}
```

### Rejected patterns

| Pattern | Example |
|---|---|
| Statement chaining | `; DROP TABLE alerts` |
| SQL comments | `--` or `/* */` |
| UNION injection | `UNION SELECT * FROM secrets` |
| Tautology | `' OR '1'='1` |
| Non-integer LIMIT | `"100; DROP"` |
| Unsafe table names | `alerts;DROP` |

These checks apply to:
- Table names (constructor)
- Tenant ID values (constructor)
- WHERE clauses (`.where()`)
- String parameter values (`.where()`)

## Incident Service

`api/services/incident_svc.py` now uses `SafeQueryBuilder` instead of raw
`.format()` interpolation:

```python
# Before (vulnerable):
query = "... LIMIT {limit}".format(limit=int(limit))

# After (safe):
qb = ch.query_builder("findings").limit(int(limit))
sql, params = qb.build()
result = ch.client.query(sql, parameters=params)
```

## Testing

Run the full tenancy test suite:

```bash
make test-tenancy
```

### Test categories

| Category | What it covers |
|---|---|
| `TestNeo4jTenantIsolation` | Every Neo4j method includes `tenant_id` in Cypher |
| `TestSafeQueryBuilder` | Builder always adds tenant filter, rejects injections |
| `TestClickHouseClientTenancy` | Every insert/query includes `tenant_id` |
| `TestCrossTenantLeakage` | Two tenants write data, no cross-contamination |
| `TestInjectionPrevention` | 13 SQL injection payloads blocked |
| `TestGraphSyncTenancy` | GraphSynchronizer inherits tenant from client |
| `TestIncidentServiceTenancy` | Incident service uses SafeQueryBuilder |

## Migration Notes

### Existing data

Existing data without `tenant_id` will not be visible to tenant-scoped
queries. To migrate:

1. **ClickHouse**: `ALTER TABLE telemetry ADD COLUMN tenant_id ...` then
   `ALTER TABLE telemetry UPDATE tenant_id = 'default' WHERE tenant_id = ''`.
2. **Neo4j**: `MATCH (n) WHERE n.tenant_id IS NULL SET n.tenant_id = 'default'`.

### API callers

All callers that construct `ClickHouseClient` or `Neo4jClient` must now pass
`tenant_id`. The default is `"default"` for backward compatibility, but
production deployments should always specify an explicit tenant.
