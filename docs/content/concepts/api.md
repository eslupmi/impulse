# API & Endpoints

!!! info
    All endpoints use the [HTTP_PREFIX](../envs.md) prefix if configured.

Except for `/livez`, `/readyz` and `/metrics`, all endpoints return `503 Service Unavailable` while the server is in **standby** mode (see [High Availability](ha.md)).

## API

The API is available under the `/api` endpoint. Interactive and schema documentation:

- `/api/docs` - Swagger UI
- `/api/openapi.json` - OpenAPI schema

### Incident actions

All incident actions use POST and require authentication when UI authentication is enabled.
Replace `{uniq_id}` with the incident ID.

| Endpoint | JSON body | Action |
| --- | --- | --- |
| `/api/incidents/{uniq_id}/freeze` | `{"until": "2099-08-02T18:00:00Z"}` | Manually freeze until an RFC3339 timestamp with a timezone. |
| `/api/incidents/{uniq_id}/task` | `{}` or no body | Create a task through the configured task management integration. |
| `/api/incidents/{uniq_id}/assign` | `{"user_id": "U123"}` | Assign a user; `user_id` must be a string. |
| `/api/incidents/{uniq_id}/unassign` | `{}` or no body | Remove the current assignment. |
| `/api/incidents/{uniq_id}/unfreeze` | `{}` or no body | Remove a manual freeze. Maintenance and inhibition freezes cannot be removed here. |

Successful actions return `{"success": true}`. Assignment and unassignment return
`{"success": false}` when the requested assignment already matches the current state.
Task creation returns `{"success": true, "result": ...}` with the integration's result.

Common errors are `401` for a missing session, `404` for an unknown incident, and `422`
for an invalid assignment or freeze body. Task creation returns `409` if a task already
exists or is being created. Freeze returns `409` if the incident is already frozen;
unfreeze returns `409` unless the incident can be manually unfrozen. Assignment and
freeze return `502` when the messenger cannot apply the action.

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



### HTTP `/auth/login` [GET]

Start UI authentication.

**Requirements:**

- Optional query parameter `next`: local path to open after login

**Responses:**

- `302 Found` - Redirect to the messenger authorization page

### HTTP `/auth/callback` [GET]

OAuth callback for UI authentication.

**Responses:**

- `302 Found` - Redirect back to the UI. Sets the session cookie when authentication succeeds

### HTTP `/auth/me` [GET]

Current UI session user.

**Responses:**

- `200 OK` - `{"authenticated": true, "user": ...}` when a session exists, `{"authenticated": false}` otherwise

### HTTP `/auth/logout` [POST]

End the UI session.

**Responses:**

- `204 No Content` - Session ended and the session cookie cleared

### other

GET `/ui_config` - UI table and display configuration.

GET `/chains_config` - messenger escalation chains, users, groups, webhooks, and timezone settings used by the UI. Authentication required when auth is enabled.

!!! warning
    `/assignment_users`, `/incidents`, `/task`, `/freeze`, and `/unfreeze` will be removed in `v4.0.0`.
    Use their `/api` equivalents for new integrations. `/assign` remains supported; the UI will switch
    to `/api/incidents/{uniq_id}/assign` and `/api/incidents/{uniq_id}/unassign` in `v4.0.0`.

GET `/assignment_users` - the same configured-user map as GET `/api/users`, keyed by configuration name.
Each user has an `id` (a string or number, depending on the messenger), `full_name`, `exists`, and other profile fields.
The UI offers users whose `exists` is true.

GET `/incidents` - the same serialized incident map as GET `/api/incidents`.

POST `/assign` - assign or unassign a user on an incident (`uniq_id`, `user_id`; `""` to unassign). Authentication required when auth is enabled.

POST `/task` - create a task for an incident (`uniq_id`), with the same result as POST `/api/incidents/{uniq_id}/task`. Authentication required when auth is enabled.

POST `/freeze` - freeze an incident (`uniq_id`, `freeze_option`: `tomorrow`, `next_monday`, `month`, `6months`), with the same result as POST `/api/incidents/{uniq_id}/freeze`. The legacy input retains UI presets; the API accepts an explicit `until` timestamp. Authentication required when auth is enabled.

POST `/unfreeze` - unfreeze a manually frozen incident (`uniq_id`), with the same result as POST `/api/incidents/{uniq_id}/unfreeze`. Authentication required when auth is enabled.

POST `/release` - release a resolved assigned incident (`uniq_id`). Authentication required when auth is enabled.

## Administer endpoints

### HTTP `/-/reload` [POST]

Reload server configuration without restart.

**Requirements:**

- Server must be in **primary** mode (returns `503` in **standby** mode)

**Responses:**

- `200 OK` - Configuration reloaded successfully
- `400 Bad Request` - Configuration reload failed
- `500 Internal Server Error` - Unexpected reload error
