<h1 align="center" style="border-bottom: none">
    <a href="https://impulse.bot" target="_blank"><img alt="Prometheus" src="logo.svg" width="50"></a> IMPulse
</h1>

<div align="center"><img src="https://github.com/eslupmi/site/blob/main/static/preview.png?raw=true" width="600"></div>

Visit [https://docs.impulse.bot](https://docs.impulse.bot) for the full documentation and examples.

## Features
- Slack, Mattermost integrations
- Twilio and another integrations using [webhooks](https://docs.impulse.bot/latest/config_file/#webhooks-examples)
- [Incident lifecycle](https://docs.impulse.bot/latest/concepts/#lifecycle) reduces incidents chaos
- Flexible [message structure](https://docs.impulse.bot/latest/concepts/#structure) you can modify
- Duty shedule ([docs](https://docs.impulse.bot/latest/config_file/#schedule-chain))

## Quick Start

*Docker installation example for Slack*

1. Use [instructions](https://docs.impulse.bot/latest/slack) to create and configure bot

2. Create directories
    ```bash
    mkdir impulse impulse/config impulse/data
    cd impulse
    ```

3. Get docker-compose.yml and config
    ```bash
    wget -O docker-compose.yml https://raw.githubusercontent.com/eslupmi/impulse/main/examples/docker-compose.yml
    wget -O config/impulse.yml https://raw.githubusercontent.com/eslupmi/impulse/main/examples/impulse.slack.yml
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
