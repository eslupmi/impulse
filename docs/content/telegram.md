# Telegram

In Telegram, we use **groups** with topics instead of **channels**.

## Create bot

Use this [instuction](https://core.telegram.org/bots/features#creating-a-new-bot). Save bot token as `TELEGRAM_BOT_TOKEN` ENV (use in 2.3 [here](installation.md#23-impulse)).

## Configure group

1. Open group, go to Menu, press "Manage group"
    - enable "Topics"
    - you can set [our icon](https://github.com/eslupmi/site/blob/main/static/logo.png?raw=true) by pressing "photo" image
    - press **Save**

2. Add the bot to your group

3. Promote the bot to administrator, enable "Manage topics"

4. Ensure that `application.admin_users` is included in all `route` groups

5. Add users from `application.chains` to their groups.

    To make it simpler you can add all `application.users` to all groups from `route` block.

6. Highly recommend mute notifications forever for group

7. Get group ID (with `@myidbot` bot)
    - add `@myidbot` bot to group
    - go to group's "General" topic and send command `/getgroupid@myidbot`
    - use group ID in `application.channels` [block](config_file.md#channels)
    - you can remove `@myidbot` bot

8. IMPulse bot should have permissions to interact with users. If you see log WARNING <b>user &lt;username&gt; not found in Telegram and will not be notified</b> try to send message from &lt;username&gt; to bot. This should help.
