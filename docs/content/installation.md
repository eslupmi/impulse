# Installation

There are two options to install IMPulse: via **Python** (3.9+) or using the **Docker** image.

Select your preferred method and continue.

## 1. Messenger

See **INTEGRATIONS** to create bot and configure your messenger.

We support integrations with [Mattermost](mattermost.md), [Slack](slack.md) and [Telegram](telegram.md). Visit their pages to learn how to create and configure a bot.

## 2. Get IMPulse

=== "python"

    Use the `<release_tag>` from [here](https://github.com/DiTsi/impulse/releases) and run:

    === "Slack"
        ```bash
        git clone --branch <release_tag> --single-branch git@github.com:DiTsi/impulse.git impulse
        cd impulse
        # for advanced configuration
        cp examples/impulse.slack.advanced.yml impulse.yml
        # for minimal configuration
        cp examples/impulse.slack.minimal.yml impulse.yml
        cp examples/.env.slack .env
        ```

    === "Mattermost"
        ```bash
        git clone --branch <release_tag> --single-branch git@github.com:DiTsi/impulse.git impulse
        cd impulse
        # for advanced configuration
        cp examples/impulse.mattermost.advanced.yml impulse.yml
        # for minimal configuration
        cp examples/impulse.mattermost.minimal.yml impulse.yml
        cp examples/.env.mattermost .env
        ```

    === "Telegram"
        ```bash
        git clone --branch <release_tag> --single-branch git@github.com:DiTsi/impulse.git impulse
        cd impulse
        # for advanced configuration
        cp examples/impulse.telegram.advanced.yml impulse.yml
        # for minimal configuration
        cp examples/impulse.telegram.minimal.yml impulse.yml
        cp examples/.env.telegram .env
        ```

=== "docker"

    === "Slack"
        ```bash
        mkdir impulse impulse/config impulse/data
        cd impulse
        wget -O docker-compose.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/docker-compose.yml
        # for advanced configuration
        wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.slack.advanced.yml
        # for minimal configuration
        wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.slack.minimal.yml
        ```

    === "Mattermost"
        ```bash
        mkdir impulse impulse/config impulse/data
        cd impulse
        wget -O docker-compose.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/docker-compose.yml
        # for advanced configuration
        wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.mattermost.advanced.yml
        # for minimal configuration
        wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.mattermost.minimal.yml
        ```

    === "Telegram"
        ```bash
        mkdir impulse impulse/config impulse/data
        cd impulse
        wget -O docker-compose.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/docker-compose.yml
        # for advanced configuration
        wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.telegram.advanced.yml
        # for minimal configuration
        wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.telegram.minimal.yml
        ```

    don't forget to replace `<release_tag>` in `docker-compose.yml` to one of the [release tags](https://github.com/DiTsi/impulse/releases).

## 3. Configure IMPulse

Modify `.env` (python) or `docker-compose.yml` (docker) with required [Environment Variables](envs.md) information.

Modify `impulse.yml` with your data. See all configurations options [here](config_file.md).

## 4. Run IMPulse

=== "python"

    ```bash
    gunicorn -w 1 -b 0.0.0.0:5000 wsgi:app
    ```

=== "docker"

    ```bash
    docker-compose up -d
    ```

## 5. Configure Alertmanger

See the [Alertmanager instruction](alertmanager.md)
