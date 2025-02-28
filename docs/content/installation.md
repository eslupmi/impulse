# Installation

There are two options to install IMPulse: **python** (3.9+) and **docker** image.

Select preferred method and move on.

## 1. Messenger

See **INTEGRATIONS** to create bot and configure your messenger.

We have integrations with [Slack](slack.md) and [Mattermost](mattermost.md). See their pages to create and configure bot.

## 2. Get IMPulse

### python

Use `<release_tag>` from [here](https://github.com/DiTsi/impulse/releases) and do:

```bash
git clone --branch <release_tag> --single-branch git@github.com:DiTsi/impulse.git impulse
cd impulse

### Slack
# for advanced configuration
cp examples/impulse.slack.advanced.yml impulse.yml
# for minimal configuration
cp examples/impulse.slack.minimal.yml impulse.yml
cp examples/.env.slack .env

### Mattermost
# for advanced configuration
cp examples/impulse.mattermost.advanced.yml impulse.yml
# for minimal configuration
cp examples/impulse.mattermost.minimal.yml impulse.yml
cp examples/.env.mattermost .env
```

### docker

```bash
mkdir impulse impulse/config impulse/data
cd impulse
wget -O docker-compose.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/docker-compose.yml

### Slack
# for advanced configuration
wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.slack.advanced.yml
# for minimal configuration
wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.slack.minimal.yml

### Mattermost
# for advanced configuration
wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.mattermost.advanced.yml
# for minimal configuration
wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.mattermost.minimal.yml
```

don't forget to replace `<release_tag>` in `docker-compose.yml` to one of the [release tags](https://github.com/DiTsi/impulse/releases).

## 3. Configure IMPulse

Modify `.env` (python) or `docker-compose.yml` (docker) with required [Environment Variables](envs.md) information.

Modify `impulse.yml` with your data. See all configurations options [here](config_file.md).

## 4. Run IMPulse

### python

```bash
gunicorn -w 1 -b 0.0.0.0:5000 wsgi:app
```

### docker

```bash
docker-compose up -d
```

## 5. Configure Alertmanger

See [Alertmanager instruction](alertmanager.md)
