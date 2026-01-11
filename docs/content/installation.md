# Installation

There are two options to install IMPulse: via **Python** (3.10 - 3.13) or using the **Docker** image.

Select your preferred method and continue.

## 1. Messenger

See **INTEGRATIONS / Messengers** menu to create bot and configure your messenger.

We support integrations with [Mattermost](integrations/messengers/mattermost.md), [Slack](integrations/messengers/slack.md) and [Telegram](integrations/messengers/telegram.md). Visit their pages to learn how to create and configure a bot.

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
    python -m main
    ```

=== "docker"

    ```bash
    docker compose up -d
    ```

To configure the host and port that IMPulse listens on, use the `LISTEN_HOST` and `LISTEN_PORT` environment variables. See [environment variables](envs.md) for more details.

## 5. Configure source of alerts

See instructions in the **INTEGRATIONS** > **Alert Sources** section of the menu.

## 6. Reverse proxy

If you are using reverse proxy and need an HTTP prefix, use the **HTTP_PREFIX** environment variable ([env](envs.md)). Don't forget to update your `impulse_address` in the configuration to include the prefix.
