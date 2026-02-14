<h1><img alt="IMPulse" src="logo.svg" width="50"> IMPulse</h1>

[![Version](https://img.shields.io/github/v/release/eslupmi/impulse?sort=semver&label=&color=555&logo=github)](https://github.com/eslupmi/impulse/releases)
[![Container](https://img.shields.io/badge/-ghcr.io%2Feslupmi%2Fimpulse-gray?logo=docker)](https://ghcr.io/eslupmi/impulse)
[![Community Helm](https://img.shields.io/badge/-community-gray?style=flat&logo=helm)](https://artifacthub.io/packages/helm/impulse/impulse)

[![Sonar](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=alert_status&label=)](https://sonarcloud.io/dashboard?id=eslupmi_impulse)

<div align="center"><img src="https://github.com/eslupmi/site/blob/main/static/ui.png?raw=true" width="700"></div>

Visit [docs.impulse.bot](https://docs.impulse.bot) for the full documentation.

## Features

- Mattermost, Slack, Telegram integrations
- Jira integration
- [Freeze](https://docs.impulse.bot/latest/buttons/#freeze) mechanism to pause incident update and silence
- Powerful [webhooks](https://docs.impulse.bot/stable/config_file/#webhooks) for Twilio, Instatus and other third-party integrations
- [Incident lifecycle](https://docs.impulse.bot/stable/concepts/#lifecycle) reduces incidents chaos
- Scheduling using providers like Google Calendar via [cloud chains](https://docs.impulse.bot/stable/config_file/#cloud-chain)
- Support for [nested chains](https://docs.impulse.bot/stable/config_file/#nested-chain) with unlimited depth
- Flexible [message structure](https://docs.impulse.bot/stable/concepts/#structure) you can modify
- Customizable [UI](https://docs.impulse.bot/stable/ui) with multi-column sorting and advanced filtering capabilities

## Quick Start

Run without messenger integration:

```bash
# Prepare "impulse" directory
git clone https://github.com/eslupmi/impulse.git impulse.bak
mkdir -p impulse/config impulse/data
cp impulse.bak/examples/docker-compose.yml impulse/docker-compose.yml
cp impulse.bak/examples/impulse.none.yml impulse/config/impulse.yml
rm -rf impulse.bak

# Replace "<release_tag>" with the latest stable Docker tag
tag=$(git ls-remote --tags https://github.com/eslupmi/impulse.git | awk -F/ '{print $NF}' | tail -n1)
sed -i "s|<release_tag>|$tag|" impulse/docker-compose.yml

# Run IMPulse without messenger integration
cd impulse
docker compose up
```

Now IMPulse is available at http://localhost:5000/.

You can try to send a test alert with:

```bash
curl -XPOST -H "Content-Type: application/json" http://localhost:5000/ -d '{"receiver":"webhook-alerts","status":"firing","alerts":[{"status":"firing","labels":{"alertname":"InstanceDown4","instance":"localhost:9100","job":"node","severity":"warning"},"annotations":{"summary":"Instanceunavailable"},"startsAt":"2024-07-28T19:26:43.604Z","endsAt":"0001-01-01T00:00:00Z","generatorURL":"http://eva:9090/graph?g0.expr=up+%3D%3D+0&g0.tab=1","fingerprint":"a7ddb1de342424cb"}],"groupLabels":{"alertname":"InstanceDown"},"commonLabels":{"alertname":"InstanceDown","instance":"localhost:9100","job":"node","severity":"warning"},"commonAnnotations":{"summary":"Instanceunavailable"},"externalURL":"http://eva:9093","version":"4","groupKey":"{}:{alertname=\"InstanceDown\"}","truncatedAlerts":0}'
```

See [documentation](https://docs.impulse.bot) and the Slack [example](https://github.com/eslupmi/impulse/blob/develop/examples/impulse.slack.yml) to configure IMPulse for your messenger.
