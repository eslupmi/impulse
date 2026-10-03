<h1><img alt="IMPulse" src="logo.svg" width="50"> IMPulse</h1>

[![Website](https://img.shields.io/badge/website-impulse.bot-blue)](https://impulse.bot) [![Documentation](https://img.shields.io/badge/docs-docs.impulse.bot-blue)](https://docs.impulse.bot) [![Container](https://img.shields.io/badge/docker-ghcr.io%2Feslupmi%2Fimpulse-blue?logo=docker)](https://ghcr.io/eslupmi/impulse) [![Community Helm](https://img.shields.io/badge/community-artifacthub.io-blue?style=flat&logo=helm)](https://artifacthub.io/packages/helm/impulse/impulse)

**IMPulse** is a ChatOps Incident Management Platform. 

It is open source, self-hosted, and IaC-ready. Designed with the KISS principle as a lightweight, single-component utility. IMPulse helps SRE, DevOps, and platform teams create and route incidents, track their status, and coordinate responders at the right time according to escalation chains.

Documentation here: https://docs.impulse.bot/stable/

![IMPulse incident management interface](https://github.com/eslupmi/site/blob/main/static/preview.png?raw=true)

## Features

- **Snoozed incidents:** [freeze](https://docs.impulse.bot/stable/concepts/incident/#freeze) incidents to handle them later
- **Inhibition rules:** [suppress](https://docs.impulse.bot/stable/concepts/inhibition/#inhibition) child incidents when a parent incident is active
- **No chaos:** incidents have a [lifecycle](https://docs.impulse.bot/stable/concepts/incident/#lifecycle) that automatically prevents duplicate incidents and reduces noise
- **Maintenance:** mute incidents during [maintenance](https://docs.impulse.bot/stable/concepts/maintenance)
- **Single Sign-On:** no extra accounts - [sign in](https://docs.impulse.bot/stable/guides/authentication/) with your chat platform
- **Templating:** Jinja2 [templates](https://docs.impulse.bot/stable/concepts/templates/) for incidents, thread messages, and Jira tasks
- **Unlimited escalation policies:** create as many [escalation policies](https://docs.impulse.bot/stable/config_file/#messengerchains) as you need, including nested
- **External notifications:** connect anything via powerful [webhooks](https://docs.impulse.bot/stable/config_file/#webhooks)
- **High availability:** run multiple IMPulse instances for [reliability](https://docs.impulse.bot/stable/concepts/ha/)
- **Minimal UI:** simple by design, customizable where it matters

## Quick start

The following steps will start IMPulse using Docker Compose with the built-in web UI, without integrating a chat messenger.

```bash
# Create directory structure
mkdir -p impulse/{config,data} && cd impulse

# Get Docker compose file and configuration example
curl -fsSL -o docker-compose.yml https://raw.githubusercontent.com/eslupmi/impulse/develop/examples/docker-compose.none.yml
curl -fsSL -o config/impulse.yml https://raw.githubusercontent.com/eslupmi/impulse/develop/examples/impulse.none.yml

# Run IMPulse
docker compose up -d
```

Now IMPulse is available at [http://localhost:5000/](http://localhost:5000/).

### Test alert

You can try to send a test alert with:

```bash
curl -XPOST -H "Content-Type: application/json" http://localhost:5000/ -d '{"receiver":"webhook-alerts","status":"firing","alerts":[{"status":"firing","labels":{"alertname":"InstanceDown4","instance":"localhost:9100","job":"node","severity":"warning"},"annotations":{"summary":"Instanceunavailable"},"startsAt":"2024-07-28T19:26:43.604Z","endsAt":"0001-01-01T00:00:00Z","generatorURL":"http://eva:9090/graph?g0.expr=up+%3D%3D+0&g0.tab=1","fingerprint":"a7ddb1de342424cb"}],"groupLabels":{"alertname":"InstanceDown"},"commonLabels":{"alertname":"InstanceDown","instance":"localhost:9100","job":"node","severity":"warning"},"commonAnnotations":{"summary":"Instanceunavailable"},"externalURL":"http://eva:9093","version":"4","groupKey":"{}:{alertname=\"InstanceDown\"}","truncatedAlerts":0}'
```

The new `firing` incident appears in the UI.

Follow the [installation guide](https://docs.impulse.bot/stable/installation/) for production deployment.

## Python packages and development

`impulse-bot` is the core application and public `impulse_messenger_api` contract. Slack, Mattermost, and Telegram are separate distributions in the [impulse-messengers repository](https://github.com/eslupmi/impulse-messengers): `impulse-slack`, `impulse-mattermost`, and `impulse-telegram`. The built-in `none` messenger needs no provider package. Existing messenger configuration and environment variable names stay the same.

The next release is `3.8.0` for core and all three messenger libraries. Core and provider versions must match; each library requires `impulse-bot==3.8.0`. Libraries have no independent version bumps: update a library to the target IMPulse version only when that IMPulse release requires library changes.

Use [uv](https://docs.astral.sh/uv/) with Python 3.10 or newer. Clone both repositories as siblings, then synchronize from the core checkout:

```bash
git clone https://github.com/eslupmi/impulse.git
git clone https://github.com/eslupmi/impulse-messengers.git
cd impulse
uv sync --locked
cp examples/impulse.none.yml impulse.yml
uv run python -m main --check
uv run python -m main
```

The default development group installs all three providers from the sibling checkout, plus test and lint tools. `pyproject.toml` declares dependencies and `uv.lock` pins resolution. Use `uv lock` after dependency changes; use `uv sync --locked` for normal development.

Build the core and each provider as wheels without publishing anything:

```bash
uv build --wheel
uv build --project ../impulse-messengers --all-packages --wheel
```

Install built artifacts into a fresh environment. Include only the provider wheels you need; each provider requires `impulse-bot==3.8.0` and is discovered through the `impulse.messengers` entry point group:

```bash
uv venv /tmp/impulse-runtime
uv pip install --python /tmp/impulse-runtime/bin/python dist/*.whl ../impulse-messengers/dist/*.whl
CONFIG_PATH=/absolute/path/to/config DATA_PATH=/absolute/path/to/data /tmp/impulse-runtime/bin/python -m main --check
CONFIG_PATH=/absolute/path/to/config DATA_PATH=/absolute/path/to/data /tmp/impulse-runtime/bin/python -m main
```

The installed core includes UI assets and Jira templates, so launching it does not require the source checkout. Filesystem template overrides continue to use the configured paths. The libraries are prepared for distribution; the commands above install local wheels and do not depend on unpublished PyPI releases. The core distribution is named `impulse-bot` because the PyPI names `impulse` and `impulse-core` belong to unrelated packages.

For a core-only container using `messenger.type: none`, run `docker build -t impulse-bot .`. To include providers, first build their wheels into `wheelhouse/`:

```bash
uv build --project ../impulse-messengers --all-packages --wheel --out-dir "$PWD/wheelhouse"
docker build -t impulse-with-messengers .
```

The Dockerfile uses the frozen core lockfile and installs any supplied provider wheels. CI checks out both repositories, uses uv for dependencies, and prepares all three wheels before building the full container. Publish compatible changes to both repositories before expecting those remote workflows to run the new extraction.
