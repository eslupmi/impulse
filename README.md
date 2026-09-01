<h1><img alt="IMPulse" src="logo.svg" width="50"> IMPulse</h1>

![IMPulse incident management interface](https://github.com/eslupmi/site/blob/main/static/preview.png?raw=true)

**An open-source, self-hosted incident management platform built around ChatOps and configuration as code.**

IMPulse helps SRE, DevOps, and platform teams route alerts, escalate incidents, coordinate responders, and manage incident workflows without introducing a heavy operational stack. It integrates with Alertmanager and Grafana, works directly in Slack, Mattermost, Telegram, or its built-in web UI, and keeps response logic under your control.

## Sites
[![Website](https://img.shields.io/badge/website-impulse.bot-blue)](https://impulse.bot) [![Documentation](https://img.shields.io/badge/docs-docs.impulse.bot-blue)](https://docs.impulse.bot)

## Artifacts
[![Container](https://img.shields.io/badge/docker-ghcr.io%2Feslupmi%2Fimpulse-blue?logo=docker)](https://ghcr.io/eslupmi/impulse) [![Community Helm](https://img.shields.io/badge/community-artifacthub.io-blue?style=flat&logo=helm)](https://artifacthub.io/packages/helm/impulse/impulse)

## Why IMPulse

Incident management platforms often grow into large control planes with their own databases, queues, service catalogs, user models, and operational dependencies.

IMPulse takes a different approach: start with the parts teams need most — alert routing, escalation, incident coordination, maintenance workflows, and ChatOps — while keeping deployment lightweight and response policy versionable as code.

IMPulse is designed to grow with your incident-management workflow while preserving a lightweight, automation-friendly architecture.

![Alertmanager sends alerts to IMPulse, which routes incidents to a messenger](docs/content/media/impulse.excalidraw.svg)

## Quick start

This path starts IMPulse with Docker Compose and the built-in web UI, without connecting a messenger.

```bash
# Create directory structure
mkdir -p impulse/{config,data} && cd impulse

# Get Docker compose file and configuration example
curl -fsSL -o docker-compose.yml https://raw.githubusercontent.com/eslupmi/impulse/master/examples/docker-compose.none.yml
curl -fsSL -o config/impulse.yml https://raw.githubusercontent.com/eslupmi/impulse/master/examples/impulse.none.yml

# Run IMPulse
docker compose up -d
```

Open [http://localhost:5000/](http://localhost:5000/). The online indicator in the UI confirms that IMPulse is running and receiving live updates.

**Send a test alert**

```bash
curl -XPOST -H "Content-Type: application/json" http://localhost:5000/ -d '{"receiver":"webhook-alerts","status":"firing","alerts":[{"status":"firing","labels":{"alertname":"InstanceDown4","instance":"localhost:9100","job":"node","severity":"warning"},"annotations":{"summary":"Instanceunavailable"},"startsAt":"2024-07-28T19:26:43.604Z","endsAt":"0001-01-01T00:00:00Z","generatorURL":"http://eva:9090/graph?g0.expr=up+%3D%3D+0&g0.tab=1","fingerprint":"a7ddb1de342424cb"}],"groupLabels":{"alertname":"InstanceDown"},"commonLabels":{"alertname":"InstanceDown","instance":"localhost:9100","job":"node","severity":"warning"},"commonAnnotations":{"summary":"Instanceunavailable"},"externalURL":"http://eva:9093","version":"4","groupKey":"{}:{alertname=\"InstanceDown\"}","truncatedAlerts":0}'
```

The new `firing` incident appears in the UI.

Follow the [installation guide](https://docs.impulse.bot/stable/installation/) for production deployment or start from the [Slack configuration example](examples/impulse.slack.yml) to connect a messenger and route real alerts.

## License

IMPulse is licensed under the [GNU General Public License v3.0](LICENSE.md).
