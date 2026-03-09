# Telegram

!!! warning "Limitations"
    See [Messenger Comparison](../../concepts/messengers.md)

In Telegram, although the configuration uses the term `channels`, they are actually implemented as groups with topics.

## Authentication

1. Open BotFather Mini App
2. Select IMPulse bot -> Bot Settings
3. In the **Web Login** section:
    - press **Switch to OpenID Connect Login** button, **Confirm**
    - press **Add an Allowed URL** button, **Add a Redirect URI**
    - enter `https://<your_domain_name>/auth/callback` as a Redirect URI
    - use "Client ID" as ENV `AUTH_CLIENT_ID`
    - use "Client Secret" as ENV `AUTH_CLIENT_SECRET`

## Create a bot

Follow this [instruction](https://core.telegram.org/bots/features#creating-a-new-bot). Save the bot token as the `TELEGRAM_BOT_TOKEN` environment variable (used in section 2.3 [here](../../installation.md#4-configure-impulse)).

## Configure groups

1. Open your group, go to the menu, and click "Manage group":
    - enable "Topics"
    - optionally, set [our logo](https://github.com/eslupmi/site/blob/main/static/logo.png?raw=true) by clicking the "photo" icon
    - click **Save**

2. Add the bot to your group

3. Promote the bot to administrator, enable "Manage topics"

4. All users from `messenger.admin_users` must be members of every group listed in the `route` block

5. Add users from `messenger.chains` to their respective groups.
       
    For simplicity, you can add all users from `messenger.users` to all groups defined in the `route` block

6. It is highly recommended to mute group notifications forever to reduce noise

7. Get the group ID (using the `@myidbot` bot)
    - add `@myidbot` bot to group
    - go to the group's "General" topic and send the command: `/getgroupid@myidbot`
    - use the returned group ID in the `messenger.channels` [configuration block](../../config_file.md#messengerchannels)
    - you can remove `@myidbot` afterwards

8. Make sure the IMPulse bot has permission to interact with users. If you see the log warning <b>"user &lt;username&gt; not found in Telegram and will not be notified"</b> - ask the user `<username>` to send a message to the bot. This usually resolves the issue.
