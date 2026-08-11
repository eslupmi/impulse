# API

IMPulse provides simple API and WebSocket endpoints for incident management and system interaction.

!!! info
    All endpoints use the [HTTP_PREFIX](../envs.md) prefix if configured.

## General endpoints

### HTTP `/` [GET]

Main page of the IMPulse web interface.

### HTTP `/` [POST]

Send a new alert for processing.

**Requirements:**

- Server must be in **primary** mode
- Request body must contain valid JSON with alert data

**Requirements:**

- UI must be enabled in configuration ([[ui](../config_file.md#ui) section])

### HTTP `/app` [POST]
### HTTP `/app` [PUT]

Handle button interactions in messengers (Slack, Mattermost, Telegram).

### HTTP `/incidents` [GET]

Get list of all incidents.

### HTTP `/metrics` [GET]

Prometheus metrics endpoint. Returns metrics in Prometheus format for monitoring and observability.

**Responses:**

- `200 OK` - Returns metrics in Prometheus format

### HTTP `/queue` [GET]

Get current processing queue state.

## Storage read API

Read-only endpoints under `/api` return the same payloads as each entity's `serialize()` method. Collection keys match path identifiers (`uniq_id` for incidents; config names for groups, users, user groups, and webhooks).

### HTTP `/api/incidents` [GET]

Get all incidents. Returns `{uniq_id: incident.serialize()}`.

### HTTP `/api/incidents/{uniq_id}` [GET]

Get one incident by `uniq_id`.

**Responses:**

- `200 OK` - Incident payload
- `404 Not Found` - Incident not found

### HTTP `/api/groups` [GET]

Get all messenger groups. Returns `{config_name: group.serialize()}` (`exists`, `id`).

### HTTP `/api/groups/{group_name}` [GET]

Get one group by config name.

**Responses:**

- `200 OK` - Group payload
- `404 Not Found` - Group not found

### HTTP `/api/users` [GET]

Get configured users only as `{config_name: User.serialize()}`. Runtime/UserStore-only users are omitted. `messenger_type` is not included.

- Slack / Mattermost: `email`, `full_name`, `id` (string), `name`, `timezone`, `username`
- Telegram: `full_name`, `id` (int), `name`, `username`

### HTTP `/api/users/{user_name}` [GET]

Get one configured user by config name.

**Responses:**

- `200 OK` - User payload
- `404 Not Found` - User not found

### HTTP `/api/user_groups` [GET]

Get all user groups. Returns `{name: user_group.serialize()}` (`users`).

### HTTP `/api/user_groups/{user_group_name}` [GET]

Get one user group by name.

**Responses:**

- `200 OK` - User group payload
- `404 Not Found` - User group not found

### HTTP `/api/webhooks` [GET]

Get all webhooks. Returns `{name: webhook.serialize()}` without authentication credentials (`data`, `json`, `url`). URL/body templates are returned without environment rendering; Jinja expressions that reference `env` are replaced with `***`.

### HTTP `/api/webhooks/{webhook_name}` [GET]

Get one webhook by name.

**Responses:**

- `200 OK` - Webhook payload
- `404 Not Found` - Webhook not found

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

### HTTP `/readyz` [GET]

Server readiness check. Used for health checks and determining server state (see [High Availability](ha.md)).

**Responses:**

- `200 OK` - Server is ready and running in **primary** mode
- `503 Service Unavailable` - Server is in **standby** mode or initializing

### HTTP `/-/reload` [POST]

Reload server configuration without restart.

**Requirements:**

- Server must be in **primary** mode (returns `503` in **standby** mode)

**Responses:**

- `200 OK` - Configuration reloaded successfully
- `400 Bad Request` - Configuration reload failed
- `500 Internal Server Error` - Unexpected reload error
