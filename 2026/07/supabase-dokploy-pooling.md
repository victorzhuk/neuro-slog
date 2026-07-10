---
title: "one supabase, many apps: connection pooling for self-hosted supabase on dokploy"
date: 2026-07-10
published: 2026-07-10T23:37:31+03:00
tags: [architecture, supabase, dokploy]
description: how to share one self-hosted supabase stack across dokploy apps without burning through postgres connections
---

I run several small Dokploy apps against one self-hosted Supabase, and their idle pools can quietly exhaust Postgres connections before any of them does real work. Transaction pooling fixes that, but it breaks session state, prepared statements, advisory locks — anything that assumes a backend sticks around. My setup uses one Postgres, PgBouncer for application traffic, one role and schema per app, and a direct Postgres connection for migrations.

## Why Postgres connections are the scarce resource

Postgres uses a process-per-connection model. Every client connection makes the postmaster fork a backend process. The commonly repeated figure is 5–10 MB of RAM per idle connection, and AWS's own benchmark of idle connections landed around 10 MB each for 100 test connections. Andres Freund's more careful 2020 measurement ("Measuring the Memory Overhead of a Postgres Connection") argues the true *incremental* overhead is under 2 MiB once you account for shared pages — so the honest range is "a couple of MB at best, up to ~10 MB in practice."

Either way it is not free, and the default `max_connections` is 100. You can raise it, but doing so increases RAM use and adds pressure on shared-memory structures, so it is not a free dial.

A single app with its own connection pool is fine. `pgxpool` on the Go side keeps, say, 10 connections warm and reuses them. The problem starts when you have five apps, each with its own `pgxpool`, each sized for its own peak, all pointed at the same Postgres.

Ten connections times five apps is fifty backends before anyone is doing real work, and on self-hosted Supabase you are not the only tenant of that database: PostgREST, GoTrue, Realtime, Storage, and the health checker all hold their own long-lived connections. App-side pooling does nothing about this. Each app pool is an island; none of them knows about the others, so their sizes add up linearly against one shared `max_connections`.

A server-side pooler fixes that. It sits in front of Postgres, accepts a large number of client connections, and multiplexes them onto a small, fixed set of real backends. In transaction pooling mode a client holds a real backend only for the duration of a transaction, then hands it back. This is how a pool of 20 backends serves 500 client connections: most of those clients are idle between queries.

## Pooling modes

Three modes matter. Session pooling assigns a backend to a client for the whole session; it is the safe default and every Postgres feature works, but it does not save you many connections. Transaction pooling assigns a backend only for a transaction; it saves the most connections and is what you want for many small apps. Statement pooling is stricter still and breaks multi-statement transactions, so skip it.

Transaction pooling is where the footguns live. Because a client's transactions can each land on a different backend, anything that relies on session state breaks: `SET`, session-level advisory locks, `LISTEN`/`NOTIFY`, and (historically) prepared statements.

## PgBouncer vs PgDog (and where Supavisor fits)

Self-hosted Supabase already ships a pooler: **Supavisor**, written in Elixir, built by Supabase for multi-tenant cloud use. In the Docker Compose stack it runs as the `supavisor` service and listens on 5432 (session) and 6543 (transaction). It works.

For a single self-hosted box running a handful of apps, though, it is a lot of machinery: it is multi-tenant by design (usernames are tenant-qualified, e.g. `postgres.your-tenant-id`), it stores encrypted config, and it is one more Elixir service to reason about. Plenty of people keep it. I wanted something smaller and more familiar to put in front of my own app roles, so I run a dedicated pooler and treat Supavisor as optional.

The two candidates are PgBouncer and PgDog.

**PgBouncer** is the default answer and has been for over a decade. It is a single-process, single-threaded proxy written in C; the PgBouncer docs note it "consumes very low memory (2kB per connection by default)" — tiny client-connection overhead compared to Postgres backends. It is boring in the way infrastructure should be boring.

The current stable release is 1.25.2, which shipped on 8 May 2026 with four CVE fixes — notably CVE-2026-6664, a pre-auth integer overflow in the SCRAM parser that can crash the pooler, so patch to 1.25.2 if you are exposing the pooler at all.

Two limitations matter for this discussion. First, single-threaded: on a many-core box one PgBouncer process saturates one core, and the workaround is running several processes with `so_reuseport`. For small apps y…

**PgDog** is the newer option: a connection pooler, load balancer, and sharding proxy written in Rust on Tokio, licensed AGPLv3. It is multi-threaded, so one process can use more than one core.

Sharding is the headline feature: PgDog parses SQL, extracts sharding keys, routes queries, and can reshard online through logical replication. For this setup, the useful part is narrower. The PgDog docs state it plainly: "It supports SET statements, LISTEN/NOTIFY, and advisory locks without breaking connection state, so your application keeps working as if it were talking to Postgres directly."

Config is TOML (`pgdog.toml` plus `users.toml`) rather than the ini/`userlist.txt` split, and it listens on 6432 by default.

PgDog is young and moving quickly; I would only put it in front of the only database if I were ready to track releases.

My recommendation:

| Situation | Choice |
| --- | --- |
| A few small apps, one Postgres, want boring and proven | **PgBouncer** |
| You need `SET`/advisory-locks/`LISTEN`-`NOTIFY` to survive transaction pooling without app changes | **PgDog** |
| Many cores and one pooler process is a CPU bottleneck | **PgDog** (multi-threaded) or multiple PgBouncer with `so_reuseport` |
| You will outgrow one Postgres and need sharding | **PgDog** |
| You want to keep what Supabase ships and don't want another service | **Supavisor** (already there) |

I use PgBouncer. The apps are small, I want the mature option, and every session-state problem PgDog solves for me is one I can also solve with schema and role design plus a bit of discipline. If I were sharding, or if rewriting apps to avoid `SET` were expensive, I would reach for PgDog.

## Schema per app

Each app gets its own Postgres schema inside the single Supabase database. Not its own database.

The reason is the pooler. Schemas give each app an ownership boundary without creating another Postgres database, but PgBouncer still creates a separate backend pool for every app role because its pool key is `(user, database)`, so schemas do not let those roles share backend connections. One database keeps backups, occasional cross-app queries, and connection accounting in one place; size each role's pool and keep their sum within the Postgres connection budget.

Provisioning one app looks like this. Do it as a superuser (`postgres` on self-hosted Supabase):

```sql
-- App role (owns its schema; used by the app and by migrations)
CREATE ROLE app_orders LOGIN PASSWORD 'change-me';

-- Its schema, owned by the role
CREATE SCHEMA app_orders AUTHORIZATION app_orders;

-- Pin the role's search_path so unqualified names resolve to its schema.
-- Applied at connection start, before any query.
ALTER ROLE app_orders SET search_path = app_orders;

-- Lock down the public schema so apps can't create objects there.
-- On Postgres 15+ CREATE on public is already revoked from PUBLIC by
-- default, but self-hosted Supabase images have historically been on
-- older majors, so do it explicitly and idempotently.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
```

Each app connects as its own role, owns its own schema, and cannot create objects in `public` or read another app's schema unless you explicitly grant it. If you want a separate least-privilege role for runtime versus migrations, create a second role with DML but not DDL and grant it into the schema, using `ALTER DEFAULT PRIVILEGES IN SCHEMA app_orders GRANT ... ON TABLES TO app_orders_rw` so future tables inherit the grants. For most small apps a single owner role per schema is enough.

Isolation between apps is enforced by ownership and the absence of grants. `app_orders` has no privileges on `app_billing`'s schema, so even if a query tried to reach across, it fails on permissions. This is coarse but real, and it does not depend on getting `search_path` exactly right at runtime — which, as we'll see, is the part that breaks under transaction pooling.

Custom app roles coexist with the Supabase role landscape. Supabase ships `postgres` (admin), `anon`, `authenticated`, and `service_role` (used by PostgREST via the `authenticator` role that logs in and switches into the others), plus service admins like `supabase_auth_admin` and `supabase_storage_admin` scoped to the `auth` and `storage` schemas.

Your `app_*` roles are just ordinary Postgres roles alongside these. They are not part of the PostgREST/JWT machinery and do not need to be. If an app never touches Supabase Auth or the REST API and just talks SQL, its role has nothing to do with `anon`/`authenticated` at all.

## Authenticating the pooler with a SECURITY DEFINER function

PgBouncer needs to verify the password a client presents. The old way is `userlist.txt`, a file of usernames and password hashes that you keep in sync by hand. With many app roles and rotating passwords that becomes a chore. The better way is `auth_query`: PgBouncer connects as a dedicated `auth_user` and runs a query to fetch the stored hash for the connecting user.

The catch is that the password hashes live in `pg_shadow` / `pg_authid`, which only superusers can read. You do not want your `auth_user` to be a superuser. The standard pattern is a `SECURITY DEFINER` function: it runs with the privileges of its owner (a superuser), so it can read the catalog, but you grant `EXECUTE` on it only to the unprivileged `auth_user`.

Create a dedicated role and a locked-down function in its own schema:

```sql
-- Unprivileged role PgBouncer uses to run auth_query.
CREATE ROLE pgbouncer_auth LOGIN PASSWORD 'change-me';

-- Keep the function out of public.
CREATE SCHEMA IF NOT EXISTS pgbouncer;
REVOKE ALL ON SCHEMA pgbouncer FROM PUBLIC;
GRANT USAGE ON SCHEMA pgbouncer TO pgbouncer_auth;

CREATE OR REPLACE FUNCTION pgbouncer.user_lookup(
    INOUT p_user   name,
    OUT   p_passwd text
)
RETURNS record
LANGUAGE sql
SECURITY DEFINER
-- Pin search_path inside the function. This is both a correctness and a
-- security measure (see CVE-2025-12819 below).
SET search_path = pg_catalog
AS $$
    SELECT rolname,
           CASE WHEN rolvaliduntil < now() THEN NULL ELSE rolpassword END
    FROM pg_authid
    WHERE rolname = p_user
      AND rolcanlogin
      AND NOT rolsuper;
$$;

-- Only the auth role may call it.
REVOKE ALL ON FUNCTION pgbouncer.user_lookup(name) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pgbouncer.user_lookup(name) TO pgbouncer_auth;
```

Two details are deliberate. The `rolvaliduntil` check mirrors what PgBouncer adopted as its default `auth_query` in 1.24.1 (CVE-2025-2291): without it, an expired password could still authenticate through the proxy. Excluding `rolsuper` means superuser hashes never pass through the pooler.

Pinning `search_path = pg_catalog` inside the function is not decoration: CVE-2025-12819 (fixed in PgBouncer 1.25.1) was an arbitrary-SQL-execution hole that required, among other things, an `auth_query` whose object references were not schema-qualified. Qualify everything and pin the path.

The examples below use `myapp-supabase-db` for the database host; substitute your Dokploy template's `${CONTAINER_PREFIX}-db` value.

The matching `pgbouncer.ini` fragment:

```ini
[databases]
postgres = host=myapp-supabase-db port=5432 dbname=postgres auth_user=pgbouncer_auth

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432

auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
auth_user = pgbouncer_auth
auth_query = SELECT p_user, p_passwd FROM pgbouncer.user_lookup($1)

pool_mode = transaction
max_client_conn = 500
default_pool_size = 20
max_db_connections = 80

; PgBouncer 1.24+: protocol-level prepared statements in transaction mode,
; enabled by default (max_prepared_statements=200). For 1.21-1.23 you must
; set non-zero explicitly; upgrade if you can.
max_prepared_statements = 200
```

`userlist.txt` now only needs one line, for `pgbouncer_auth` itself, so PgBouncer can make its initial connection. The function must exist in every database `auth_query` runs against; here that is just `postgres`. On the Postgres side, make sure `pg_hba.conf` lets `pgbouncer_auth` in (scoped to the pooler's address), and that both the pooler and Postgres agree on `scram-sha-256`.

## The search_path trap under transaction pooling

`search_path` is the subtle failure mode. The design above pins it per role so apps can use unqualified names, but transaction pooling preserves that guarantee only when each app has its own login role.

`SET search_path = app_orders` is session state. If your app issues it once after connecting and expects it to stick, transaction pooling breaks it: the next transaction may run on a different backend that never saw the `SET`, or worse, on a backend that some other client set differently. Session-level `SET` is unsafe under transaction pooling, period.

What actually works, in rough order of preference:

**`ALTER ROLE ... SET search_path`** is the reliable one, with a condition. This sets the parameter at connection start, as part of establishing the backend, so it is applied before any query regardless of pooling mode — but only if each app connects as its own role and PgBouncer keeps per-`(user, database)` pools.

That is exactly the design above: one role per app, so each app's pool is its own set of backends, each started with the right `search_path`. If you instead shared one login role across apps and switched schema at runtime, this would fall apart. Per-role `search_path` plus per-app pooler users is the combination that makes it safe.

**Schema-qualify everything.** The bulletproof option is to not depend on `search_path` at all and write `app_orders.orders` everywhere. With sqlc this is painless: write your queries and schema against qualified names and the generated Go carries them through. This removes an entire class of pooling bug. I do this for anything shared or security-sensitive and lean on per-role `search_path` for the rest.

**`SET LOCAL`** is transaction-scoped, so it is safe under transaction pooling — it applies only within the current transaction and is discarded at commit. Useful if you must set a parameter for one unit of work, but it means wrapping reads in explicit transactions, which is friction.

**`server_reset_query = DISCARD ALL`** does not make session state safe. PgBouncer ignores it in transaction mode by default; `server_reset_query_always = 1` can force a reset after every transaction, but the next transaction can still land on another backend.

**`track_extra_parameters = search_path`** exists but is a trap for this setup. PgBouncer can only track parameters that Postgres reports back to the client via `GUC_REPORT`, and stock Postgres does not report `search_path` — only Citus 12+ (or Postgres 18, where the relevant change landed) makes it do so.

And enabling `track_extra_parameters = search_path` together with `auth_user` and a non-schema-qualified `auth_query` is precisely the CVE-2025-12819 configuration. Leave it alone unless you are on Postgres 18 and know exactly why you want it.

My approach: per-role `search_path` via `ALTER ROLE` for ergonomics, schema-qualified queries (via sqlc) for anything I care about, and never a session-level `SET` in application code.

## Migrations with goose

Migrations are the other thing transaction pooling breaks, and the failure is nasty because it looks like success.

I use goose (`pressly/goose`). goose can take a session-level Postgres advisory lock before running migrations so that two instances starting at once do not migrate concurrently — the `SessionLocker` from `github.com/pressly/goose/v3/lock`, created with `lock.NewPostgresSessionLocker()`. It uses `pg_try_advisory_lock` with a fixed advisory lock ID derived from the string "goose", retrying in a loop (configurable via `WithLockTimeout`). The lock is session-scoped: held until the backend releases it or disconnects.

The fix is simple: **migrations bypass the pooler and connect directly to Postgres.** Apps connect through the pooler port; migration jobs connect to Postgres on 5432. In Dokploy I run migrations as a separate init container that connects direct, using a distinct `MIGRATION_DATABASE_URL`, and only after it exits do the app containers (pointed at the pooler) start.

```go
package main

import (
	"context"
	"database/sql"
	"io/fs"
	"os"

	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/pressly/goose/v3"
	"github.com/pressly/goose/v3/lock"
)

func runMigrations(ctx context.Context, migrationsFS fs.FS) error {
	// MIGRATION_DATABASE_URL points DIRECTLY at Postgres (port 5432),
	// never at the pooler. Advisory locks need a stable session.
	db, err := sql.Open("pgx", os.Getenv("MIGRATION_DATABASE_URL"))
	if err != nil {
		return err
	}
	defer db.Close()

	sessionLocker, err := lock.NewPostgresSessionLocker(
		lock.WithLockTimeout(15, 120), // retry every 15s, up to 120 times
	)
	if err != nil {
		return err
	}

	provider, err := goose.NewProvider(
		goose.DialectPostgres,
		db,
		migrationsFS,
		goose.WithSessionLocker(sessionLocker),
	)
	if err != nil {
		return err
	}

	_, err = provider.Up(ctx)
	return err
}
```

Run it from the CLI the same way — point the connection string at the direct connection, not the pooler:

```bash
# Direct to Postgres, bypassing PgBouncer/Supavisor.
goose -dir ./migrations postgres \
  "postgres://app_orders:change-me@myapp-supabase-db:5432/postgres?search_path=app_orders" up
```

If you genuinely cannot get a direct connection, the alternative is `pg_advisory_xact_lock`, which is transaction-scoped and released automatically at commit, so it survives transaction pooling. But goose's built-in locker is session-based, so the practical answer is: give migrations a direct line to Postgres and keep the pooler out of it.

## Wiring it into Dokploy

Dokploy deploys Supabase from a Docker Compose template. The database is the `db` service (container name `${CONTAINER_PREFIX}-db`, e.g. `myapp-supabase-db`; the upstream Supabase compose uses `supabase-db`), and the stack ships Supavisor as the `supavisor` service (`${CONTAINER_PREFIX}-pooler`, upstream `supabase-pooler`).

The relevant env vars and their defaults: `POSTGRES_PORT=5432` (session), `POOLER_PROXY_PORT_TRANSACTION=6543` (transaction), `POOLER_TENANT_ID=your-tenant-id`, `POOLER_DEFAULT_POOL_SIZE=20`, `POOLER_MAX_CLIENT_CONN=100`. Internally every Supabase service reaches Postgres via `POSTGRES_HOST=db`.

Dokploy templates pin image tags, and upstream Supabase moves independently; check the current template before copying connection strings or assuming service names.

The important Dokploy-specific fact is networking. In my setup, each service deployed through the Dokploy UI lands on its own isolated network, so a separately deployed app cannot reach Supabase Postgres by name out of the box. The shared network is `dokploy-network`, and you join it by declaring it external in your compose file:

```yaml
services:
  orders-api:
    image: registry.example.com/orders-api:latest
    restart: unless-stopped
    environment:
      # App traffic goes through the pooler.
      DATABASE_URL: "postgres://app_orders:change-me@pgbouncer:6432/postgres"
      # Migrations go direct to Postgres.
      MIGRATION_DATABASE_URL: "postgres://app_orders:change-me@myapp-supabase-db:5432/postgres?search_path=app_orders"
    networks:
      - dokploy-network

  pgbouncer:
    image: edoburu/pgbouncer:v1.25.2-p0
    restart: unless-stopped
    volumes:
      - ./pgbouncer/pgbouncer.ini:/etc/pgbouncer/pgbouncer.ini:ro
      - ./pgbouncer/userlist.txt:/etc/pgbouncer/userlist.txt:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -p 6432 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - dokploy-network

networks:
  dokploy-network:
    external: true
```

The pooler's `[databases]` entry points at `host=myapp-supabase-db port=5432` — the internal Docker DNS name of the Supabase Postgres container on the shared network. Apps point `DATABASE_URL` at the `pgbouncer` service on 6432; migration jobs point `MIGRATION_DATABASE_URL` at `myapp-supabase-db` on 5432.

If you skip your own PgBouncer and use the shipped Supavisor instead, the transaction-mode string is `postgres://postgres.your-tenant-id:PASSWORD@supavisor:6543/postgres` — note the tenant-qualified username, which is a Supavisor requirement, not a Postgres one.

I leave `container_name` unset for app services and let Dokploy manage their names.

## The Go client behind a transaction pooler

`pgx` (v5) defaults to `QueryExecModeCacheStatement`: it prepares statements, names them with a hash, and caches them. On PgBouncer 1.24+ with `max_prepared_statements` set, that default just works — keep it.

If your pooler supports protocol-level prepared statements — PgBouncer 1.24+ does by default, PgBouncer 1.21–1.23 does when `max_prepared_statements` is non-zero, and PgDog supports them — you can keep the default. pgx's `CacheStatement` mode works in that case, and you get the planning-time savings prepared statements give you.

Do not call `Conn.Prepare` or SQL-level `DEALLOCATE` yourself behind PgBouncer: individual `DEALLOCATE` is forwarded to Postgres; only `DEALLOCATE ALL` and `DISCARD ALL` clear PgBouncer's tracked prepared-statement state.

If your pooler does not support them — older PgBouncer, or Supavisor transaction mode, which does not support prepared statements — disable automatic prepared statements. Set the exec mode to `exec`, which uses the extended protocol without server-side named statements.

`QueryExecModeSimpleProtocol` is the most conservative option and is what the pgx author recommends for maximum pooler compatibility, at the cost of client-side parameter interpolation and a slightly different type-handling path. Avoid the `describe`-based modes (`CacheDescribe`, `DescribeExec`) behind a pooler that swaps the backend between round trips.

For that fallback, set it in the connection string (`?default_query_exec_mode=exec`) or on the config:

```go
package main

import (
	"context"
	"os"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func newPool(ctx context.Context) (*pgxpool.Pool, error) {
	// DATABASE_URL points at PgBouncer (port 6432).
	cfg, err := pgxpool.ParseConfig(os.Getenv("DATABASE_URL"))
	if err != nil {
		return nil, err
	}

	// Behind a transaction pooler without prepared-statement support,
	// disable pgx's automatic prepared statements. Equivalent to
	// ?default_query_exec_mode=exec in the DSN.
	cfg.ConnConfig.DefaultQueryExecMode = pgx.QueryExecModeExec

	// Size the app pool. See the sizing note below.
	cfg.MaxConns = 10
	cfg.MinConns = 0
	cfg.MaxConnIdleTime = 60 * time.Second
	cfg.MaxConnLifetime = 30 * time.Minute

	return pgxpool.NewWithConfig(ctx, cfg)
}
```

**Sizing.** There are three numbers and they must line up. Each app's `pgxpool.MaxConns`, times the number of instances of that app, is the client-connection load it puts on the pooler — bounded by PgBouncer's `max_client_conn` (500 above, cheap to raise).

What actually hits Postgres is `default_pool_size` per `(user, database)` pool. The real constraint is the sum of `default_pool_size` across all your app roles plus Supabase's own baseline connections, which must stay under Postgres `max_connections`.

With five apps at `default_pool_size = 20` you are asking for up to 100 backends before counting Supabase's own services, so either lower `default_pool_size` per app, set per-app pool overrides, or raise `max_connections` deliberately. `max_db_connections` gives you a global ceiling as a backstop.

Keep app-side `MaxConns` modest: behind a transaction pooler, idle app connections are cheap (they cost a pooler client slot, not a backend), so you do not need large per-app pools.

## What I'd do differently, and what I wouldn't

The schema-per-app plus per-role-`search_path` design has held up well. The single best decision was schema-qualifying anything important in sqlc rather than trusting `search_path` at runtime; it removed a category of intermittent bug that only shows up under load, which is the worst kind.

I would not reach for PgDog yet for this specific job, despite liking what it does. The apps are small, PgBouncer is proven, and the session-state problems PgDog solves are ones I have already designed around. The day I need sharding, or the day rewriting an app to stop using session `SET` costs more than adopting a fast-moving Rust proxy, that calculus flips.

The one thing to get right on day one is the migration path. Running migrations through the transaction pooler will appear to work in development and then hang or corrupt state under concurrency in production. Give migrations a direct connection to Postgres, keep the pooler for app traffic, and the rest is routine.

## Further reading

- [PgBouncer configuration and changelog](https://pgbouncer.org)
- [PgDog documentation](https://docs.pgdog.dev)
- [Supavisor and Supabase self-hosting](https://supabase.com/docs/guides/self-hosting/docker)
- [pgx query execution modes](https://pkg.go.dev/github.com/jackc/pgx/v5)
- [goose provider and session locking](https://pressly.github.io/goose)
- [PostgreSQL schemas and advisory locks](https://postgresql.org/docs/current)
- [Dokploy templates and Docker Compose](https://docs.dokploy.com)
