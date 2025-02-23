# Environment Variables

Environment variables are created in `.env` file for python installation or in `docker-compose.yml` for docker installation. 

| Variable | Description | Default | Required |
|-|-|-|-|
| DATA_PATH | path to data directory | ./data | - |
| CONFIG_PATH | path to `impulse.yml` directory | ./ | - |
| LOG_LEVEL | [Log level](https://github.com/DiTsi/impulse/blob/main/app/logging.py#L15) | INFO | - |
| MATTERMOST_ACCESS_TOKEN | [Mattermost 'Access Token'](mattermost.md) | | for Mattermost |
| SLACK_BOT_USER_OAUTH_TOKEN | [Slack 'Bot User OAuth Token'](slack.md) | | for Slack |
| SLACK_VERIFICATION_TOKEN | [Slack 'Verification Token'](slack.md) | | for Slack |
