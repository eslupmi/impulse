# Slack

## Authentication

1. Use [https://&lt;your_domain&gt;/auth/callback](https://<your_domain>/auth/callback) as ENV `AUTH_REDIRECT_URL`[↰](../../envs.md)
2. Go to [Slack Apps](https://api.slack.com/apps), select IMPulse app
3. In the **Basic Information** section:
    - use "Client ID" as ENV `AUTH_CLIENT_ID`[↰](../../envs.md)
    - use "Client Secret" as ENV `AUTH_CLIENT_SECRET`[↰](../../envs.md)
4. In the **OAuth & Permissions** section:
    - in **Redirect URLs** subsection add IMPulse URL
    - press **Save URLs** button

## Create a bot

1. Go to [Slack Apps](https://api.slack.com/apps) and click button **Create New App**.
2. Select **From scratch**.
3. Set the **App Name** to "IMPulse" and choose your workspace.

## Configure the bot

1. In the **Interactivity & Shortcuts** section:
    - enable "Interactivity"
    - set the **Request URL** to [https://&lt;your_domain&gt;/app](https://<your_domain>/app)

2. In the **OAuth & Permissions** section:
    - in **Scopes** subsection add these "Bot Token Scopes":
        - channels:read
        - chat:write
        - chat:write.customize
        - chat:write.public
        - groups:read
        - im:read
        - im:write
        - mpim:read
        - usergroups:read
        - users:read
    - we highly recommend to add the IP address of your IMPulse server in white list in **Restrict API Token Usage** subsection
    - in **OAuth Tokens** click the button **Install to &lt;your_workspace&gt;**, then **Allow**
    - use "Bot User OAuth Token" as ENV `SLACK_BOT_USER_OAUTH_TOKEN`[↰](../../envs.md) (used [here](../../installation.md#4-configure-impulse))
3. In **Basic Information** section:
    - in the **App Credentials** subsection:
        - use "Verification Token" as ENV `SLACK_VERIFICATION_TOKEN`[↰](../../envs.md) (used [here](../../installation.md#4-configure-impulse))
    - in **Display Information** subsection:
        - you can set [our logo](https://github.com/eslupmi/site/blob/main/static/logo.png?raw=true) as **App icon**

## Configure channels

1. To use the IMPulse bot in private channels, you **must** manually invite it. Run this command in each required private channel:

    ```
    /invite @IMPulse
    ```

2. All users from `messenger.admin_users`[↰](../../config_file.md#messengeradmin_users) **must** be present in every channel listed in the `route`[↰](../../config_file.md#route) block.

3. Add users from `messenger.chains`[↰](../../config_file.md#messengerchains) to their respective channels.

4. We recommend configuring IMPulse channels for all `messenger.users`[↰](../../config_file.md#messengerusers) as follows:
    - right-click on the channel
    - select "Change notifications"
    - choose "Mentions" and check the option "Also include @channel and @here"
    - Click **Save Changes**.

## Get group ID

To copy group ID:

- In any thread mention group using `@`
- Click it to open
- Press **"..." (More actions)** button
- **Copy group ID** button
