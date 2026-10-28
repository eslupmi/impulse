# Environment Variables

Environment variables are created in `.env` file for python installation or in `docker-compose.yml` for docker installation.

!!! info "Required variables"

    Variables marked with "*" are mandatory, but only if the feature in the "Used for" column is used.

| Variable | Description | Default | Used for |
|-|-|-|-|
| AUTH_CLIENT_ID * | OAuth Client ID | | for [authentication](guides/authentication.md) |
| AUTH_CLIENT_SECRET * | OAuth Client Secret | | for [authentication](guides/authentication.md) |
| AUTH_REDIRECT_URL * | OAuth Redirect URL | | for [authentication](guides/authentication.md) |
| CHAIN_PROVIDER_DAYS_TO_SYNC | How many days will be synced | 7 | for [cloud chain](config_file.md#cloud-chains) |
| CHAIN_PROVIDER_MAX_EVENTS | Maximum events which will be synced | 10 | for [cloud chain](config_file.md#cloud-chains) |
| CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS | Sync interval, seconds | 60 | for [cloud chain](config_file.md#cloud-chains) |
| CONFIG_PATH | Path to `impulse.yml`[↰](config_file.md) directory | ./ | - |
| CORS_ALLOWED_ORIGINS | Сomma-separated list of origins<br> allowed to make cross-origin<br> requests to the server | http://localhost:5000 | for [UI](concepts/ui.md) |
| DATA_PATH | Path to data directory | ./data | for [filesystem](concepts/storage.md#filesystem) storage |
| GOOGLE_SERVICE_ACCOUNT_FILE | Path to Google service account file | ./key.json | for [cloud chain](config_file.md#cloud-chains) |
| HTTP_PREFIX | HTTP prefix for reverse proxy deployments<br/>(e.g., `/impulse`) | | - |
| HTTP_PROXY | HTTP proxy URL for outbound HTTP requests<br/> | | - |
| HTTPS_PROXY | HTTPS proxy URL for outbound HTTPS requests<br/> | | - |
| JIRA_API_TOKEN * | Jira API token for Basic Auth | | for [task management](integrations/task_management/jira.md) |
| JIRA_BASE_URL * | Jira base URL<br/>(e.g., [https://your-domain.atlassian.net](https://your-domain.atlassian.net)) | | for [task management](integrations/task_management/jira.md) |
| JIRA_USER_EMAIL * | Jira user email for Basic Auth | | for [task management](integrations/task_management/jira.md) |
| LISTEN_HOST | Host to listen on | 0.0.0.0 | - |
| LISTEN_PORT | Port to listen on | 5000 | - |
| LOG_LEVEL | Log [level](https://docs.python.org/3/library/logging.html#logging-levels) | INFO | - |
| MATTERMOST_ACCESS_TOKEN * | Mattermost 'Access Token' | | for [Mattermost](integrations/messengers/mattermost.md) |
| NO_PROXY | Comma-separated hosts that bypass the proxy<br/> | | - |
| SLACK_BOT_USER_OAUTH_TOKEN * | Slack 'Bot User OAuth Token' | | for [Slack](integrations/messengers/slack.md) |
| SLACK_VERIFICATION_TOKEN * | Slack 'Verification Token' | | for [Slack](integrations/messengers/slack.md) |
| STORAGE_BACKEND | Data [storage](concepts/storage.md) backend: "filesystem" or "s3" | filesystem | - |
| STORAGE_S3_ACCESS_KEY_ID | Explicit S3 access key ID | | for [s3](concepts/storage.md#s3) storage |
| STORAGE_S3_BUCKET_NAME * | Existing S3 bucket for persisted data | | for [s3](concepts/storage.md#s3) storage |
| STORAGE_S3_ENDPOINT_URL * | S3 endpoint URL | | for [s3](concepts/storage.md#s3) storage |
| STORAGE_S3_REGION | Explicit S3 region | | for [s3](concepts/storage.md#s3) storage |
| STORAGE_S3_SECRET_ACCESS_KEY | Explicit S3 secret key | | for [s3](concepts/storage.md#s3) storage |
| TELEGRAM_BOT_TOKEN * | Telegram 'Bot Token' | | for [Telegram](integrations/messengers/telegram.md) |

??? warning "Development variables"

    Optional `DEV_` overrides for local development and mocked messengers. Unset values keep the built-in defaults.

    | Variable | Description | Default | Required |
    |-|-|-|-|
    | DEV_MESSENGER_CUSTOM_ADDRESS | Override Slack/Telegram API base URL | | - |
    | DEV_MESSENGER_RATE_LIMIT | Override messenger HTTP request limit (`0` disables limiting) | | - |
    | DEV_MESSENGER_RATE_WINDOW | Override messenger HTTP rate-limit window, seconds | | - |
