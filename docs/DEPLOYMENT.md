# Docker deployment

The current people-search slice runs as two stateless services. The API image
contains Python 3.13 and the application installed from `backend/uv.lock`, without
development dependencies or a reload watcher. The web image builds Expo using
Node.js 26 and `npm ci`, then serves only the exported files with unprivileged
Nginx. Node.js and the Expo development server are absent from the web runtime.
The images use versioned base-image tags; rebuild with `make docker-build` to
pull base-image updates. Dependency changes still require lockfile updates.

## Build and start

Docker Engine or Docker Desktop with Compose v2 or later is required. From the
repository root, with runtime configuration already exported in your shell:

```sh
make docker-up
```

Open <http://localhost:8080>. The command builds both images, starts the services
in the background, and waits up to 120 seconds for health checks. It can be
repeated to rebuild and apply changes. Use `make docker-down` to stop and remove
this Compose stack. The app has no persistent storage in the current slice.

The Make targets pass `--env-file /dev/null` to Compose, so configuration comes
from the process environment. Build contexts contain only explicitly allowed
application inputs. Both services run as non-root users, drop Linux capabilities,
and use read-only root filesystems with a temporary `/tmp` filesystem.

## Runtime configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `LUMIERE_WEB_PORT` | `8080` | Published host port for the web service. |
| `LUMIERE_BIND_ADDRESS` | `127.0.0.1` | Host interface to publish; use `0.0.0.0` for direct access from other hosts. |
| `LUMIERE_IMAGE_REGISTRY` | `docker.io` | Image registry |
| `LUMIERE_IMAGE_PREFIX` | `lumiere/codex` | Image prefix, optionally including a namespace. |
| `LUMIERE_IMAGE_TAG` | `latest` | Tag shared by the API and web images. |
| `LUMIERE_TMDB_TOKEN` | Unset | Backend provider configuration for live searches, as described in the README. |
| `LUMIERE_LOG_LEVEL` | `INFO` | API log level. |
| `LUMIERE_CORS_ORIGINS` | `[]` | JSON array of allowed cross-origin clients; the bundled web app uses the same origin. |
| `LUMIERE_TELEMETRY_ENABLED` | `false` | Enable backend Logfire export. |
| `LOGFIRE_TOKEN` | Unset | Existing Logfire export configuration when telemetry is enabled. |

Application configuration is supplied to the API at runtime. The frontend build
sets `EXPO_PUBLIC_API_URL` to an empty string, producing relative `/api/` requests.
Changing that variable on a running web container does not change the bundle.
The API is accessible only on the Compose network at `api:8000`; only the web
service publishes a host port. The API's `/docs` and `/openapi.json` endpoints
remain internal.

For example, to run behind a host-based reverse proxy on a different port:

```sh
LUMIERE_WEB_PORT=9080 make docker-up
```

Terminate HTTPS at your deployment platform's ingress or reverse proxy and
forward traffic to the web service's port 8080. When the proxy runs on the host,
use the loopback-published port. When it runs in Docker, attach it to the same
network and forward to `web:8080`. Serve the app at the domain root. Certificates
and a hosting provider are configured by the deployment environment.

## Registry-based deployment

The same images can be promoted between environments. On the build machine,
choose an image prefix and a release tag and authenticate Docker to your registry:

```sh
export LUMIERE_IMAGE_REGISTRY=ghcr.io
export LUMIERE_IMAGE_PREFIX=your-org/lumiere
export LUMIERE_IMAGE_TAG=release-001
make docker-build
docker compose --env-file /dev/null -f compose.yaml push
```

Copy `compose.yaml` to the deployment host, export the same registry, image prefix and tag
along with that environment's application configuration, and run:

```sh
docker compose --env-file /dev/null -f compose.yaml pull
docker compose --env-file /dev/null -f compose.yaml up --detach --no-build --wait --wait-timeout 120
```

Build for the deployment host's CPU architecture. Ordinary Compose builds target
the local Docker engine's architecture. For mixed ARM64/AMD64 hosts, use Docker
Buildx to publish both Dockerfiles as multi-platform images with the same tags.

## Health and verification

`/healthz` checks Nginx; `/health` proxies to the API's process-liveness endpoint.
Neither checks provider availability. Compose waits for API health before
starting the web service. Both containers have health checks and restart on
process exit; Docker does not automatically restart an unhealthy running process.
Nginx refreshes Docker DNS resolution so API container replacement does not
require rebuilding or restarting the web service. Nginx access logging is off.

After installing frontend dependencies and Playwright Chromium as described in
the README, run:

```sh
make docker-check
```

For a different published port, also set the browser test URL:

```sh
LUMIERE_DOCKER_URL=http://127.0.0.1:9080 make docker-check
```

The smoke tests load the production JavaScript, verify same-origin search
requests through Nginx to FastAPI, exercise the real invalid-input response
without calling the provider, and check navigation fallback and missing-asset
responses. They do not require live provider configuration or telemetry export.
The separate Docker job in GitHub Actions builds and runs the same checks.

The container layout follows the [uv Docker guidance](https://docs.astral.sh/uv/guides/integration/docker/)
and [Compose health-based startup guidance](https://docs.docker.com/compose/how-tos/startup-order/).
