# API

IMPulse provides simple API and WebSocket endpoints for incident management and system interaction.

!!! info
    All endpoints use the [HTTP_PREFIX](envs.md) prefix if configured.

## Requests

### HTTP `/livez` [GET]

Server liveness check. Used for Kubernetes liveness probes to determine if the container is alive.

**Responses:**

- `200 OK` - Container is alive (returns 200 in both primary and standby modes)

### HTTP `/readyz` [GET]

Server readiness check. Used for health checks and determining server state (see [High Availability](ha.md)).

**Responses:**

- `200 OK` - Server is ready and running in primary mode
- `503 Service Unavailable` - Server is in standby mode or initializing

### HTTP `/` [GET]

Main page of the IMPulse web interface.

### HTTP `/` [POST]

Send a new alert for processing.

**Requirements:**

- Server must be in primary mode
- Request body must contain valid JSON with alert data

**Requirements:**

- UI must be enabled in configuration ([[ui](config_file.md/#ui) section])

### HTTP `/app` [POST]
### HTTP `/app` [PUT]

Handle button interactions in messengers (Slack, Mattermost, Telegram).

### HTTP `/incidents` [GET]

Get list of all incidents.

### HTTP `/queue` [GET]

Get current processing queue state.

### WebSocket `/ws`

WebSocket connection for receiving real-time incident updates.

**Requirements:**

- Server must be in `active` mode (see [High Availability](ha.md))
- Connection will be closed with code `1008` if server is in standby mode
