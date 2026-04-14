# Mattermost

## Authentication

1. Use [https://&lt;your_domain&gt;/auth/callback](https://<your_domain>/auth/callback) as ENV `AUTH_REDIRECT_URL`[↰](../../envs.md)
2. Go to **menu (3×3 dots)** > **System Console** > **Integrations** > **OAuth 2.0 Applications**, click **Add OAuth 2.0 Application**:
    - set parameters:
        - set "Is Trusted" to **No** [](check.md)
        - set "Is Public Client" to **No**
        - set "Display Name" to **IMPulse OAuth**
        - set "Description" to **-**
        - set "Homepage" to the same as [messenger.impulse_address](../../config_file.md#messengerimpulse_address)
        - set "Callback URLs" same as `AUTH_REDIRECT_URL`[↰](../../envs.md))
    - press **Save**
    - use "Client ID" as ENV `AUTH_CLIENT_ID`[↰](../../envs.md)
    - use "Client Secret" as ENV `AUTH_CLIENT_SECRET`[↰](../../envs.md)
    - press **Done**

## Create a bot

1. Go to **menu (3×3 dots)** > **System Console** > **Integrations** > **Bot Accounts**:
    - set **Enable Bot Account Creation** to `True` and press **Save**

2. Go to **menu (3×3 dots)** > **Integarations** > **Bot Accounts**:
    - click **Add Bot Account**
    - set **Username** to "impulse"
    - optionally set [our logo](https://github.com/eslupmi/site/blob/develop/static/logo.png?raw=true) as the **Bot Icon**
    - set **Display Name** to "IMPulse"
    - set **Role** to "System Admin"
    - click **Create Bot Account**
    - copy the "Token" and use it as the `MATTERMOST_ACCESS_TOKEN`[↰](../../envs.md) environment variable (see [step 2.3 here](../../installation.md#4-configure-impulse))
    - click **Done**

## Configure the bot

1. Go to **menu (3×3 dots)** > **System Console** > **User Management** > **Teams**:
    - press on your Team
    - press the button **Add Members**
    - type "impulse" in search, select it and press the button **Add**
    - press the button **Save**

## Configure channels

1. To use IMPulse bot in private channels you **must** add it manually. Run this command in all necessary private channels:

    ```
    /invite @impulse
    ```

2. Users listed in `messenger.admin_users`[↰](../../config_file.md#messengeradmin_users) **must** be present in all channels defined in `route`[↰](../../config_file.md#route).

3. Users mentioned in `messenger.chains`[↰](../../config_file.md#messengerchains) should be added to their respective channels.
    
4. We recommend configuring IMPulse channels for all `messenger.users`[↰](../../config_file.md#messengerusers) as follows:
    - select the channel in main list and press on it
    - click the **View Info** icon (i) in the top right, click **Notifications Preferences**
    - in the "Notify me about..." choose "Mentions, direct messages, and keywords only"
    - click **Save**.

## Get group IDs

```bash
MATTERMOST_URL="<your_mattermost_address>"
MATTEMROST_TOKEN="<your_mattermost_bot_token>"
curl -s -H "Authorization: Bearer $MATTEMROST_TOKEN" "$MATTERMOST_URL/api/v4/groups"
```
