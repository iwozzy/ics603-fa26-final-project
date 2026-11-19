# App-prefixed configuration

Use `LUMIERE_` for all application-owned environment variables, including
migrations and the operator-facing site address. This makes ownership clear
and avoids collisions with other applications. The user approved this change
in the configuration discussion.

## Approaches

Prefixing every tool's environment would require adapting external consumers.
Leaving all names unchanged preserves collisions. The selected approach is to
prefix application-owned variables, preserve tool-defined `OTEL_*`, `POSTGRES_*`,
and `EXPO_*` names, and translate `LUMIERE_SITE_ADDRESS` to Caddy's `SITE_ADDRESS`
in Compose.

Use Pydantic's `env_prefix` without changing Python field names. Alembic reads
`LUMIERE_MIGRATION_DATABASE_URL`. Update both Compose stacks, the placeholder
example, tests, and current README instructions together. Existing prefixed
test controls retain their names. The fixture server's app-owned `FIXTURE_PATH`
becomes `LUMIERE_TEST_FIXTURE_PATH` in both its Docker image and consumer.
No compatibility aliases are needed.

Keep defaults, validation, explicit migrations, and environment loading behavior
unchanged. Do not read or modify local environment files. Historical design and
implementation documents retain the variable names used at their creation.

Verify prefixed loading, ignored unprefixed settings, existing validation and
constructor injection, the unit/API/client suite, lint, Compose rendering with
synthetic inputs, and isolated database/browser checks if available.
