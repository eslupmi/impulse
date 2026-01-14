# Installation

## 1. Configure Messenger

=== "Slack"

    - [Create](integrations/messengers/slack.md/#create-a-bot) an IMPulse bot
    - [Configure](integrations/messengers/slack.md/#configure-the-bot) the bot
    - [Configure](integrations/messengers/slack.md/#configure-channels) channels you use for incidents

=== "Mattermost"

    - [Create](integrations/messengers/mattermost.md/#create-a-bot) an IMPulse bot
    - [Configure](integrations/messengers/mattermost.md/#configure-the-bot) the bot
    - [Configure](integrations/messengers/mattermost.md/#configure-channels) channels you use for incidents

=== "Telegram"
    
    - [Create](integrations/messengers/telegram.md#create-a-bot) an IMPulse bot
    - [Configure](integrations/messengers/telegram.md#configure-groups) groups you use for incidents

## 2. Configure source of alerts

=== "Alertmanager"

    - Set properly [Group and repeat intervals](alertmanager.md/#group-and-repeat-intervals)
    - Configure IMPulse as [receiver](alertmanager.md/#receiver)
    - Move [route](alertmanager.md/#routing) from alertmanager to [impulse.yml](config_file.md/#route) 

=== "Grafana"

    - Set properly [Group and repeat intervals](grafana.md/#group-and-repeat-intervals)
    - [Configure](grafana.md/#contact-point) IMPulse contact point

## 3. Get IMPulse

=== "Docker"

    ```bash
    mkdir impulse impulse/config impulse/data
    cd impulse
    wget -O docker-compose.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/docker-compose.yml
    wget -O config/impulse.yml https://raw.githubusercontent.com/DiTsi/impulse/develop/examples/impulse.slack.yml
    ```

=== "Python"

    Use the last `<release_tag>` from [here](https://github.com/DiTsi/impulse/releases) and run:

    ```bash
    git clone --branch <release_tag> --single-branch https://github.com/eslupmi/impulse.git impulse
    cd impulse
    cp examples/impulse.slack.yml impulse.yml
    cp examples/env.slack .env
    ```

    !!! warning ""

        Don't forget to replace `<release_tag>` in `docker-compose.yml` to one of the [release tags](https://github.com/DiTsi/impulse/releases).

## 4. Configure IMPulse

=== "Docker"

    - Modify [environment](envs.md) in `docker-compose.yml`
    - Modify [configuration](config_file.md)

=== "Python"

    - Modify [environment](envs.md) in `.env`
    - Modify [configuration](config_file.md)

## 5. Run IMPulse

=== "Docker"

    ```bash
    docker-compose up -d
    ```

=== "Python"

    ```bash
    python -m main
    ```

To configure the host and port that IMPulse listens on, use the `LISTEN_HOST` and `LISTEN_PORT` [environment variables](envs.md).

## 6. Reverse proxy

If you are using reverse proxy and need an HTTP prefix (e.g. `/impulse`), use the **HTTP_PREFIX** [environment variable](envs.md). Don't forget to update [impulse_address](config_file.md#messengerimpulse_address) to include the prefix.
