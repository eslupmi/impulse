# API & Endpoints

!!! info
    All endpoints use the [HTTP_PREFIX](../envs.md) prefix if configured.

Except for `/livez`, `/readyz` and `/metrics`, all endpoints return `503 Service Unavailable` while the server is in **standby** mode (see [High Availability](ha.md)).

## API

The API is available under the `/api` endpoint. Interactive and schema documentation:

- `/api/docs` - Swagger UI
- `/api/openapi.json` - OpenAPI schema

## General endpoints

### HTTP `/` [GET]

Main page of the IMPulse web interface.

**Requirements:**

- UI must be enabled in configuration ([[ui](../config_file.md#ui) section])

### HTTP `/` [POST]

Send a new alert for processing.

**Requirements:**

- Request body must contain valid JSON with alert data

### HTTP `/app` [POST]
### HTTP `/app` [PUT]

Handle button interactions in messengers (Slack, Mattermost, Telegram).

**Responses:**

- `200 OK` - Returns metrics in Prometheus format

### WebSocket `/ws`

WebSocket connection for receiving real-time incident updates.

**Requirements:**

- Server must be in **primary** mode (see [High Availability](ha.md))
- Connection will be closed with code `1008` if server is in **standby** mode

## Service endpoints

### HTTP `/livez` [GET]

Server liveness check. Used for Kubernetes liveness probes to determine if the container is alive.

**Responses:**

- `200 OK` - Container is alive (returns `200` in both **primary** and **standby** modes)

### HTTP `/metrics` [GET]

Prometheus metrics endpoint. Returns metrics in Prometheus format for monitoring and observability.

### HTTP `/queue` [GET]

Get current processing queue state.


### HTTP `/readyz` [GET]

Server readiness check. Used for health checks and determining server state (see [High Availability](ha.md)).

**Responses:**

- `200 OK` - Server is ready and running in **primary** mode
- `503 Service Unavailable` - Server is in **standby** mode or initializing

## Administer endpoints

### HTTP `/-/reload` [POST]

Reload server configuration without restart.

**Requirements:**

- Server must be in **primary** mode (returns `503` in **standby** mode)

**Responses:**

- `200 OK` - Configuration reloaded successfully
- `400 Bad Request` - Configuration reload failed
- `500 Internal Server Error` - Unexpected reload error
