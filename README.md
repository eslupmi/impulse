<h1><img alt="IMPulse" src="logo.svg" width="50"> IMPulse</h1>

[![Release](https://img.shields.io/github/v/release/eslupmi/impulse?sort=semver)](https://github.com/eslupmi/impulse/releases)
[![Docker](https://img.shields.io/badge/ghcr.io-eslupmi/impulse-blue?logo=docker)](https://ghcr.io/eslupmi/impulse)
[![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/impulse&color=grey)](https://artifacthub.io/packages/search?repo=impulse)

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=alert_status)](https://sonarcloud.io/dashboard?id=eslupmi_impulse)
<!-- [![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=sqale_rating)](https://sonarcloud.io/dashboard?id=eslupmi_impulse)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=bugs)](https://sonarcloud.io/dashboard?id=eslupmi_impulse)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=coverage)](https://sonarcloud.io/dashboard?id=eslupmi_impulse)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=duplicated_lines_density)](https://sonarcloud.io/dashboard?id=eslupmi_impulse)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=reliability_rating)](https://sonarcloud.io/dashboard?id=eslupmi_impulse)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=security_rating)](https://sonarcloud.io/dashboard?id=eslupmi_impulse)
[![Technical Debt](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=sqale_index)](https://sonarcloud.io/dashboard?id=eslupmi_impulse)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=vulnerabilities)](https://sonarcloud.io/dashboard?id=eslupmi_impulse) -->



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
docker-compose up
```

Now IMPulse is available at http://localhost:5000/.

You can try to send a test alert with:

```bash
curl -XPOST -H "Content-Type: application/json" http://localhost:5000/ -d '{"receiver":"webhook-alerts","status":"firing","alerts":[{"status":"firing","labels":{"alertname":"InstanceDown4","instance":"localhost:9100","job":"node","severity":"warning"},"annotations":{"summary":"Instanceunavailable"},"startsAt":"2024-07-28T19:26:43.604Z","endsAt":"0001-01-01T00:00:00Z","generatorURL":"http://eva:9090/graph?g0.expr=up+%3D%3D+0&g0.tab=1","fingerprint":"a7ddb1de342424cb"}],"groupLabels":{"alertname":"InstanceDown"},"commonLabels":{"alertname":"InstanceDown","instance":"localhost:9100","job":"node","severity":"warning"},"commonAnnotations":{"summary":"Instanceunavailable"},"externalURL":"http://eva:9093","version":"4","groupKey":"{}:{alertname=\"InstanceDown\"}","truncatedAlerts":0}'
```

See [documentation](https://docs.impulse.bot) and the Slack [example](https://github.com/eslupmi/impulse/blob/develop/examples/impulse.slack.yml) to configure IMPulse for your messenger.
