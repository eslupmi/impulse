# Installation

There are two options to install IMPulse: pure python (3.9+), docker image.

Select preferred method and move on.

## 1. Get

### python

Use `<release_tag>` from [here](https://github.com/DiTsi/impulse/releases) and do:

```bash
git clone --branch <release_tag> --single-branch git@github.com:DiTsi/impulse.git impulse
cd impulse

# for Slack
cp examples/impulse.slack.yml impulse.yml
cp examples/.env.slack .env

# for Mattermost
cp examples/impulse.mattermost.yml impulse.yml
cp examples/.env.mattermost .env
```

### docker

```bash
mkdir impulse impulse/config impulse/data
cd impulse
wget -O docker-compose.yml https://raw.githubusercontent.com/DiTsi/impulse/main/examples/docker-compose.yml

# for Slack
wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/main/examples/impulse.slack.yml

# for Mattermost
wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/main/examples/impulse.mattermost.yml
```

don't forget to replace `<release_tag>` in `docker-compose.yml` to one of the [release tags](https://github.com/DiTsi/impulse/releases).

## 2. Configure

### 2.1. Messenger

See **INTEGRATIONS** to configure your messenger.

We have integrations with [Slack](slack.md) and [Mattermost](mattermost.md). See their pages to create and configure bot.

### 2.2. Alertmanager

All code examples below are for [`alertmanager.yml`](https://prometheus.io/docs/alerting/latest/configuration/).

#### 2.2.1. set repeat_interval


Set the sum of `repeat_interval` and `group_interval` options less than [`incident.timeouts.firing`](https://github.com/DiTsi/impulse/blob/main/examples/impulse.slack.yml) (default `6h`):
```yaml
route:
  repeat_interval: 354m
  group_interval: 5m
```
The explanation is [here](concepts.md#unknown).

#### 2.2.2. move routing

IMPulse's [route](config_file.md#route) is similar to Alertmanager's, but simpler.

When using IMPulse as the only one incident manager, you can move full your Alertmanager's [`route`](https://prometheus.io/docs/alerting/latest/configuration/#route) block from `alertmanager.yml` to `impulse.yml`. Don't forget to remove all unused instructions and replcae all `receiver` instrustions with `chain` and `channel`. Fill it correctly.

Details [here](config_file.md#route).

#### 2.2.3. modify receiver

Set IMPulse as default receiver:

```yaml
receivers:
- name: 'impulse'
  webhook_configs:
  - url: 'http://<impulse_host>:<impulse_port>/'

route:
  receiver: 'impulse'
```

### 2.3. IMPulse

Modify `.env` (python) or `docker-compose.yml` (docker) with required [Environment Variables](envs.md) information.

Modify `impulse.yml` with your data. See all configurations options [here](config_file.md).

## 3. Run

Run this way for **python** installation:

```bash
gunicorn -w 1 -b 0.0.0.0:5000 wsgi:app
```

or for **docker**:

```bash
docker-compose up -d
```
