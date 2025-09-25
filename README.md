<h1><img alt="IMPulse" src="logo.svg" width="50"> IMPulse</h1>

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Release](https://img.shields.io/github/v/release/eslupmi/impulse?sort=semver)](https://github.com/eslupmi/impulse/releases)
[![Docker](https://img.shields.io/badge/ghcr.io-eslupmi/impulse-blue?logo=docker)](https://ghcr.io/eslupmi/impulse)

<div align="center"><img src="https://github.com/eslupmi/site/blob/main/static/ui.png?raw=true" width="700"></div>

Visit [docs.impulse.bot](https://docs.impulse.bot) for the full documentation.

## Features
- Mattermost, Slack, Telegram integrations
- Twilio and another integrations using [webhooks](https://docs.impulse.bot/stable/config_file/#webhooks)
- [Incident lifecycle](https://docs.impulse.bot/stable/concepts/#lifecycle) reduces incidents chaos
- Scheduling using providers like Google Calendar via [cloud chains](https://docs.impulse.bot/stable/config_file/#cloud-chain)
- Support for [nested chains](https://docs.impulse.bot/stable/config_file/#nested-chain) with unlimited depth
- Flexible [message structure](https://docs.impulse.bot/stable/concepts/#structure) you can modify
- Customizable [UI](https://docs.impulse.bot/stable/ui) with multi-column sorting and advanced filtering capabilities

## Quick Start

*Docker installation example for Slack*

1. Use [instructions](https://docs.impulse.bot/stable/slack) to create and configure bot

2. Create directories
    ```bash
    mkdir impulse impulse/config impulse/data
    cd impulse
    ```

3. Get docker-compose.yml and config
    ```bash
    wget -O docker-compose.yml https://raw.githubusercontent.com/eslupmi/impulse/develop/examples/docker-compose.yml
    wget -O config/impulse.yml https://raw.githubusercontent.com/eslupmi/impulse/develop/examples/impulse.slack.yml
    ```

4. Modify `config/impulse.yml` with actual data

5. Replace `<release_tag>` in `docker-compose.yml` with latest tag from [here](https://github.com/eslupmi/impulse/releases) and set environment variables `SLACK_BOT_USER_OAUTH_TOKEN` and `SLACK_VERIFICATION_TOKEN`

6. Run
    ```bash
    docker-compose up
    ```

7. Test

    To ensure IMPulse works fine send test alert:

    ```bash
    curl -XPOST -H "Content-Type: application/json" http://localhost:5000/ -d '{"receiver":"webhook-alerts","status":"firing","alerts":[{"status":"firing","labels":{"alertname":"InstanceDown4","instance":"localhost:9100","job":"node","severity":"warning"},"annotations":{"summary":"Instanceunavailable"},"startsAt":"2024-07-28T19:26:43.604Z","endsAt":"0001-01-01T00:00:00Z","generatorURL":"http://eva:9090/graph?g0.expr=up+%3D%3D+0&g0.tab=1","fingerprint":"a7ddb1de342424cb"}],"groupLabels":{"alertname":"InstanceDown"},"commonLabels":{"alertname":"InstanceDown","instance":"localhost:9100","job":"node","severity":"warning"},"commonAnnotations":{"summary":"Instanceunavailable"},"externalURL":"http://eva:9093","version":"4","groupKey":"{}:{alertname=\"InstanceDown\"}","truncatedAlerts":0}'
    ```
