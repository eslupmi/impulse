# Environment Variables

Environment variables are created in `.env` file for python installation or in `docker-compose.yml` for docker installation.

| Variable | Description | Default | Required |
|-|-|-|-|
| AUTH_CLIENT_ID | OAuth Client ID | | for [authentication](guides/authentication.md) |
| AUTH_CLIENT_SECRET | OAuth Client Secret | | for [authentication](guides/authentication.md) |
| AUTH_REDIRECT_URL | OAuth Redirect URL | | for [authentication](guides/authentication.md) |
| CHAIN_PROVIDER_DAYS_TO_SYNC | How many days will be synced<br/>(for [cloud chain](config_file.md#cloud-chains)) | 7 | - |
| CHAIN_PROVIDER_MAX_EVENTS | Maximum events which will be synced<br/>(for [cloud chain](config_file.md#cloud-chains)) | 10 | - |
| CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS | Sync interval, seconds<br/>(for [cloud chain](config_file.md#cloud-chains)) | 60 | - |
| CONFIG_PATH | Path to `impulse.yml`[↰](config_file.md) directory | `./` | - |
| CORS_ALLOWED_ORIGINS | Сomma-separated list of origins<br> allowed to make cross-origin<br> requests to the server | [http://localhost:5000](http://localhost:5000) | for UI |
| DATA_PATH | Path to data directory | `./data` | - |
| GOOGLE_SERVICE_ACCOUNT_FILE | Path to Google service account file<br/>(for [cloud chain](config_file.md#cloud-chains)) | `./key.json` | - |
| HTTP_PREFIX | HTTP prefix for reverse proxy deployments<br/>(e.g., `/impulse`) | | - |
| HTTP_PROXY | HTTP proxy URL for outbound HTTP requests<br/> | | - |
| HTTPS_PROXY | HTTPS proxy URL for outbound HTTPS requests<br/> | | - |
| JIRA_API_TOKEN | Jira API token for Basic Auth | | for [task management](integrations/task_management/jira.md) |
| JIRA_BASE_URL | Jira base URL<br/>(e.g., [https://your-domain.atlassian.net](https://your-domain.atlassian.net)) | | for [task management](integrations/task_management/jira.md) |
| JIRA_USER_EMAIL | Jira user email for Basic Auth | | for [task management](integrations/task_management/jira.md) |
| LISTEN_HOST | Host to listen on | 0.0.0.0 | - |
| LISTEN_PORT | Port to listen on | 5000 | - |
| LOG_LEVEL | [Log level](https://github.com/DiTsi/impulse/blob/develop/app/logging.py#L15) | INFO | - |
| MATTERMOST_ACCESS_TOKEN | [Mattermost 'Access Token'](integrations/messengers/mattermost.md) | | for Mattermost |
| NO_PROXY | Comma-separated hosts that bypass the proxy<br/> | | - |
| SLACK_BOT_USER_OAUTH_TOKEN | [Slack 'Bot User OAuth Token'](integrations/messengers/slack.md) | | for Slack |
| SLACK_VERIFICATION_TOKEN | [Slack 'Verification Token'](integrations/messengers/slack.md) | | for Slack |
| TELEGRAM_BOT_TOKEN | [Telegram 'Bot Token'](integrations/messengers/telegram.md) | | for Telegram |
