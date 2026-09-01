<h1><img alt="IMPulse" src="logo.svg" width="50"> IMPulse</h1>

**An open-source, self-hosted incident management platform built around ChatOps and configuration as code.**

IMPulse helps SRE, DevOps, and platform teams route alerts, escalate incidents, coordinate responders, and manage incident workflows without introducing a heavy operational stack. It integrates with Alertmanager and Grafana, works directly in Slack, Mattermost, Telegram, or its built-in web UI, and keeps response logic under your control.

[![Website](https://img.shields.io/badge/website-impulse.bot-blue)](https://impulse.bot)
[![Documentation](https://img.shields.io/badge/docs-docs.impulse.bot-blue)](https://docs.impulse.bot/stable/)
[![Container](https://img.shields.io/badge/container-ghcr.io%2Feslupmi%2Fimpulse-blue?logo=docker)](https://github.com/eslupmi/impulse/pkgs/container/impulse)
[![Community Helm chart](https://img.shields.io/badge/community_chart-Artifact_Hub-blue?logo=helm)](https://artifacthub.io/packages/helm/impulse/impulse)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE.md)

![IMPulse incident management interface](https://github.com/eslupmi/site/blob/main/static/preview.png?raw=true)

## Why IMPulse

Incident management platforms often grow into large control planes with their own databases, queues, service catalogs, user models, and operational dependencies.

IMPulse takes a different approach: start with the parts teams need most — alert routing, escalation, incident coordination, maintenance workflows, and ChatOps — while keeping deployment lightweight and response policy versionable as code.

IMPulse is designed to grow with your incident-management workflow while preserving a lightweight, automation-friendly architecture.

![Alertmanager sends alerts to IMPulse, which routes incidents to a messenger](docs/content/media/impulse.excalidraw.svg)

## Core capabilities

| Area                    | What IMPulse provides                                                                                                                                                                                    |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Alert intake            | Alertmanager-compatible webhooks and Grafana contact points                                                                                                                                              |
| Routing                 | Recursive, Alertmanager-style matcher rules that select a channel and escalation chain                                                                                                                   |
| Escalation & scheduling | Simple, nested, scheduled, Google Calendar-backed, and UI-managed chains with user, group, wait, nested-policy, and webhook steps                                                                        |
| Incident response       | Assignment, take/release controls, manual freeze, matcher-based inhibition, maintenance windows, and Jira task creation                                                                                  |
| Collaboration           | Slack, Mattermost, Telegram, thread notifications, Slack/Mattermost user groups, and customizable Jinja message templates                                                                                |
| Incident lifecycle      | `firing`, `resolved`, `unknown`, and `closed` states with configurable lifecycle timeouts and historical retention                                                                                       |
| Incident visibility     | Real-time web UI with configurable columns, filters, sorting, highlighting, incident details, and historical incidents                                                                                   |
| Operations              | One-service deployment, local persistent state, configuration validation on startup and reload, REST API with OpenAPI documentation, Prometheus metrics, health endpoints, and primary/standby operation |

See the [features](https://impulse.bot/#features) for details.

## Integrations


| Purpose               | Supported integrations                                                                                                                                                                                                                    |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Alert sources         | [Alertmanager](https://docs.impulse.bot/stable/alertmanager/), [Grafana](https://docs.impulse.bot/stable/grafana/)                                                                                                                        |
| Messengers            | [Slack](https://docs.impulse.bot/stable/integrations/messengers/slack/), [Mattermost](https://docs.impulse.bot/stable/integrations/messengers/mattermost/), [Telegram](https://docs.impulse.bot/stable/integrations/messengers/telegram/) |
| Escalation scheduling | [Google Calendar](https://docs.impulse.bot/stable/integrations/calendars/google/)                                                                                                                                                         |
| Task management       | [Jira](https://docs.impulse.bot/stable/integrations/task_management/jira/)                                                                                                                                                                |
| Outbound automation   | Templated HTTP webhooks, with examples for Instatus, Twilio, Zvonok, and custom integrations                                                                                                                                              |
## Quick start

This path starts the latest tagged release with Docker Compose and the built-in web UI, without connecting a messenger.

### Prerequisites

- Git
- Docker with the Compose plugin



### 1. Prepare the release

```bash
git clone https://github.com/eslupmi/impulse.git
cd impulse

release_tag="$(git tag --sort=-v:refname | head -n 1)"
git checkout --detach "$release_tag"

mkdir -p runtime/config runtime/data
cp examples/docker-compose.yml runtime/docker-compose.yml
cp examples/impulse.none.yml runtime/config/impulse.yml
sed -i "s|<release_tag>|$release_tag|" runtime/docker-compose.yml
```



### 2. Start IMPulse

```bash
cd runtime
docker compose up -d
```

Open [http://localhost:5000/](http://localhost:5000/). The online indicator in the UI confirms that IMPulse is running and receiving live updates.

### 3. Send a test alert

```bash
curl -XPOST -H "Content-Type: application/json" http://localhost:5000/ -d '{"receiver":"webhook-alerts","status":"firing","alerts":[{"status":"firing","labels":{"alertname":"InstanceDown4","instance":"localhost:9100","job":"node","severity":"warning"},"annotations":{"summary":"Instanceunavailable"},"startsAt":"2024-07-28T19:26:43.604Z","endsAt":"0001-01-01T00:00:00Z","generatorURL":"http://eva:9090/graph?g0.expr=up+%3D%3D+0&g0.tab=1","fingerprint":"a7ddb1de342424cb"}],"groupLabels":{"alertname":"InstanceDown"},"commonLabels":{"alertname":"InstanceDown","instance":"localhost:9100","job":"node","severity":"warning"},"commonAnnotations":{"summary":"Instanceunavailable"},"externalURL":"http://eva:9093","version":"4","groupKey":"{}:{alertname=\"InstanceDown\"}","truncatedAlerts":0}'
```

The new `firing` incident appears in the UI.

Follow the [installation guide](https://docs.impulse.bot/stable/installation/) for production deployment or start from the [Slack configuration example](examples/impulse.slack.yml) to connect a messenger and route real alerts.

## Configuration and deployment

IMPulse uses a single `impulse.yml` configuration file for its primary declarative configuration. The main sections define:

- messenger users, groups, channels, escalation chains, and templates;
- incident notifications, lifecycle timeouts, and retention;
- recursive routes and Alertmanager-style matchers;
- inhibition rules and external webhooks;
- Jira task management; and
- web UI columns, filters, sorting, and colors.

Some runtime-managed data, including maintenance windows and UI-managed schedules, is stored separately under the configured data path.

IMPulse validates `impulse.yml` at startup and will not start with invalid configuration. A failed reload leaves the currently valid configuration running. Configuration can be reloaded with a `HUP` signal or the `/-/reload` endpoint. See [check and reload](https://docs.impulse.bot/stable/concepts/check/) for details.

For production deployments, review:

- [environment variables](https://docs.impulse.bot/stable/envs/) for listen addresses, data/config paths, proxy settings, and credentials;
- [high availability](https://docs.impulse.bot/stable/concepts/ha/) for primary/standby behavior and readiness routing;
- [`/livez`](https://docs.impulse.bot/stable/concepts/api/), [`/readyz`](https://docs.impulse.bot/stable/concepts/api/), and [`/metrics`](https://docs.impulse.bot/stable/concepts/api/) for health checks and monitoring; and
- [versioning and upgrades](https://docs.impulse.bot/stable/versioning/) before changing major versions.

## Documentation and support

- [Documentation](https://docs.impulse.bot/stable/)
- [Changelog](CHANGELOG.md)
- [GitHub Discussions](https://github.com/orgs/eslupmi/discussions)
- [Issue tracker](https://github.com/eslupmi/impulse/issues)
- [support@impulse.bot](mailto:support@impulse.bot)

## License

IMPulse is licensed under the [GNU General Public License v3.0](LICENSE.md).
