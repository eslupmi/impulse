<h1><img alt="IMPulse" src="logo.svg" width="50"> IMPulse</h1>

**The lightweight, configuration-as-code incident response engine for Alertmanager and Grafana. One service. Filesystem-backed state. Works where your engineers already work.**

IMPulse turns grouped alerts into trackable incidents in Slack, Mattermost, Telegram, or its built-in web UI. Route by labels, notify on-call responders through escalation policies, and coordinate assignment, freezes, maintenance, and Jira task creation with one application service, one `impulse.yml` file, and filesystem-backed state.

[![Website](https://img.shields.io/badge/website-impulse.bot-blue)](https://impulse.bot)
[![Documentation](https://img.shields.io/badge/docs-docs.impulse.bot-blue)](https://docs.impulse.bot/stable/)
[![Container](https://img.shields.io/badge/container-ghcr.io%2Feslupmi%2Fimpulse-blue?logo=docker)](https://github.com/eslupmi/impulse/pkgs/container/impulse)
[![Community Helm chart](https://img.shields.io/badge/community_chart-Artifact_Hub-blue?logo=helm)](https://artifacthub.io/packages/helm/impulse/impulse)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE.md)

<div align="center"><img alt="IMPulse incident management interface" src="https://github.com/eslupmi/site/blob/main/static/preview.png?raw=true" width="960"></div>

## Why IMPulse

Full on-call platforms manage services, teams, rotations, responders, and incidents in their own control plane. IMPulse takes a smaller operational role: Alertmanager or Grafana remains the alert source, chat remains the response workspace, and IMPulse adds routing, on-call escalation, and incident state between them.

- **Operate fewer moving parts.** The default deployment is one application service with mounted configuration and data directories. There is no database server, message broker, or cache to provision.
- **Define response policy as code.** Recursive routes, escalation policies, schedules, inhibition rules, maintenance windows, webhooks, and Jinja templates live in `impulse.yml`, where they can be reviewed and versioned with the rest of your infrastructure.
- **Respond in existing channels.** In a messenger, each incident is a message; notifications and events stay in its thread. Responders can take, release, assign, freeze, and create a Jira task from the incident controls.
- **Cover practical on-call workflows.** Escalation policies—called chains in configuration—can notify users and groups, wait, call webhooks, nest other policies, follow schedules, read Google Calendar, or use shifts managed in the web UI.
- **Keep deployment and data under your control.** Run IMPulse with Docker or Python, persist state under a configurable data path, and connect Slack, Mattermost, Telegram, or no messenger at all.
- **Know when alert state may be stale.** In addition to `firing` and `resolved`, IMPulse tracks `unknown` and `closed` states with configurable timeouts and history retention.

This boundary is deliberate. IMPulse is a fit when your team already has monitoring and collaboration tools and wants self-hosted alert routing, escalation, and incident response without operating another database-backed control plane.

![Alertmanager sends alerts to IMPulse, which routes incidents to a messenger](docs/content/media/impulse.excalidraw.svg)

<div align="center"><img alt="A firing IMPulse incident with responder controls in Slack" src="docs/content/media/slack_firing.excalidraw.svg" width="520"></div>

## Core capabilities

| Area | What IMPulse provides |
| --- | --- |
| Alert intake | Alertmanager-compatible webhooks and Grafana contact points |
| Routing | Recursive, Alertmanager-style matcher rules that select a channel and escalation chain |
| On-call escalation | Simple, nested, scheduled, Google Calendar-backed, and UI-managed policies with user, group, wait, nested-policy, and webhook steps |
| Incident response | Assignment, take/release controls, manual freeze, matcher-based inhibition, maintenance windows, and Jira task creation |
| Collaboration | Slack, Mattermost, Telegram, thread notifications, Slack/Mattermost user groups, and customizable Jinja message templates |
| Incident visibility | Real-time web UI with configurable columns, filters, sorting, highlighting, details, and historical incidents |
| Operations | One-service deployment, filesystem-backed state, configuration validation on startup and reload, REST API with OpenAPI documentation, Prometheus metrics, health endpoints, and primary/standby operation |

Explore the [incident lifecycle](https://docs.impulse.bot/stable/concepts/incident/), [configuration reference](https://docs.impulse.bot/stable/config_file/), and [API and service endpoints](https://docs.impulse.bot/stable/concepts/api/) for the complete behavior.

## Integrations

| Purpose | Supported integrations |
| --- | --- |
| Alert sources | [Alertmanager](https://docs.impulse.bot/stable/alertmanager/), [Grafana](https://docs.impulse.bot/stable/grafana/) |
| Messengers | [Slack](https://docs.impulse.bot/stable/integrations/messengers/slack/), [Mattermost](https://docs.impulse.bot/stable/integrations/messengers/mattermost/), [Telegram](https://docs.impulse.bot/stable/integrations/messengers/telegram/) |
| Escalation scheduling | [Google Calendar](https://docs.impulse.bot/stable/integrations/calendars/google/) |
| Task management | [Jira](https://docs.impulse.bot/stable/integrations/task_management/jira/) |
| External notifications | Templated HTTP webhooks, with examples for Instatus, Telegram, Twilio, and Zvonok |

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

Open [http://localhost:5000/](http://localhost:5000/). The online indicator in the UI confirms that it is receiving live updates.

### 3. Send a test alert

```bash
curl --fail-with-body \
  --header 'Content-Type: application/json' \
  --data @- \
  http://localhost:5000/ <<'JSON'
{
  "version": "4",
  "groupKey": "InstanceDown-node",
  "status": "firing",
  "receiver": "webhook-alerts",
  "groupLabels": {
    "alertname": "InstanceDown",
    "service": "node"
  },
  "commonLabels": {
    "alertname": "InstanceDown",
    "service": "node",
    "severity": "warning"
  },
  "commonAnnotations": {
    "summary": "A node exporter instance is unavailable"
  },
  "externalURL": "http://alertmanager:9093",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "InstanceDown",
        "service": "node",
        "severity": "warning",
        "instance": "localhost:9100"
      },
      "annotations": {
        "summary": "A node exporter instance is unavailable"
      },
      "startsAt": "2024-07-28T19:26:43.604Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://prometheus:9090/graph?g0.expr=up%20%3D%3D%200"
    }
  ]
}
JSON
```

The new `firing` incident appears in the UI. Follow the [installation guide](https://docs.impulse.bot/stable/installation/) or start from the [Slack configuration example](examples/impulse.slack.yml) to connect a messenger and route real alerts.

## Configuration and deployment

IMPulse uses a single `impulse.yml` configuration file. The main sections define:

- messenger users, groups, channels, escalation chains, and templates;
- incident notifications, lifecycle timeouts, and retention;
- recursive routes and Alertmanager-style matchers;
- inhibition rules and external webhooks;
- Jira task management; and
- web UI columns, filters, sorting, and colors.

IMPulse validates `impulse.yml` at startup and will not start with an invalid configuration. A failed reload leaves the current valid configuration running. Configuration can be reloaded with a `HUP` signal or the `/-/reload` endpoint. See [check and reload](https://docs.impulse.bot/stable/concepts/check/) for details.

For production deployments, review:

- [environment variables](https://docs.impulse.bot/stable/envs/) for listen addresses, data/config paths, proxy settings, and credentials;
- [high availability](https://docs.impulse.bot/stable/concepts/ha/) for primary/standby behavior and readiness routing;
- [`/livez`, `/readyz`, and `/metrics`](https://docs.impulse.bot/stable/concepts/api/) for health checks and monitoring; and
- [versioning and upgrades](https://docs.impulse.bot/stable/versioning/) before changing major versions.

## Documentation and support

- [Documentation](https://docs.impulse.bot/stable/)
- [Changelog](CHANGELOG.md)
- [GitHub Discussions](https://github.com/orgs/eslupmi/discussions)
- [Issue tracker](https://github.com/eslupmi/impulse/issues)
- [support@impulse.bot](mailto:support@impulse.bot)

## License

IMPulse is licensed under the [GNU General Public License v3.0](LICENSE.md).
