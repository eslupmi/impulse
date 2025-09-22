# Installation

There are two options to install IMPulse: via **Python** (3.9+) or using the **Docker** image.

Select your preferred method and continue.

## 1. Messenger

See **INTEGRATIONS** to create bot and configure your messenger.

We support integrations with [Mattermost](mattermost.md), [Slack](slack.md) and [Telegram](telegram.md). Visit their pages to learn how to create and configure a bot.

## 2. Get IMPulse

=== "python"

    Use the last `<release_tag>` from [here](https://github.com/DiTsi/impulse/releases) and run:

    ```bash
    git clone --branch <release_tag> --single-branch https://github.com/eslupmi/impulse.git impulse
    cd impulse
    cp examples/impulse.slack.yml impulse.yml
    cp examples/env.slack .env
    ```


=== "docker"

    ```bash
    mkdir impulse impulse/config impulse/data
    cd impulse
    wget -O docker-compose.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/docker-compose.yml
    wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.slack.yml
    ```

    don't forget to replace `<release_tag>` in `docker-compose.yml` to one of the [release tags](https://github.com/DiTsi/impulse/releases).

## 3. Configure IMPulse

Modify environment in `.env` (python) or `docker-compose.yml` (docker).

Modify configuration in `impulse.yml`.

## 4. Run IMPulse

=== "python"

    ```bash
    uvicorn main:app --host 0.0.0.0 --port 5000 --workers 1
    ```

=== "docker"

    ```bash
    docker-compose up -d
    ```

## 5. Configure Alertmanger

See the [Alertmanager instruction](alertmanager.md)
