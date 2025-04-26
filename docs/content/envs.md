# Environment Variables

Environment variables are created in `.env` file for python installation or in `docker-compose.yml` for docker installation. 

| Variable | Description | Default | Required |
|-|-|-|-|
| CHAIN_PROVIDER_DAYS_TO_SYNC | How many days will be synced<br/>(for [cloud chain](config_file.md#cloud-chain)) | 7 | - |
| CHAIN_PROVIDER_MAX_EVENTS | Maximum events which will be synced<br/>(for [cloud chain](config_file.md#cloud-chain)) | 10 | - |
| CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS | Sync interval<br/>(for [cloud chain](config_file.md#cloud-chain)) | 60 | - |
| CONFIG_PATH | path to `impulse.yml` directory | ./ | - |
| DATA_PATH | path to data directory | ./data | - |
| GOOGLE_SERVICE_ACCOUNT_FILE | path to Google service account file<br/>(for [cloud chain](config_file.md#cloud-chain)) | ./key.json | - |
| LOG_LEVEL | [Log level](https://github.com/DiTsi/impulse/blob/develop/app/logging.py#L15) | INFO | - |
| MATTERMOST_ACCESS_TOKEN | [Mattermost 'Access Token'](mattermost.md) | | for Mattermost |
| SLACK_BOT_USER_OAUTH_TOKEN | [Slack 'Bot User OAuth Token'](slack.md) | | for Slack |
| SLACK_VERIFICATION_TOKEN | [Slack 'Verification Token'](slack.md) | | for Slack |
| TELEGRAM_BOT_TOKEN | [Telegram 'Bot Token'](telegram.md) | | for Telegram |
