# Mattermost

## Create bot

1. Go to Menu (3×3 dots) > System Console > Integrations > Bot Accounts:
    - set "Enable Bot Account Creation" to `True` and press **Save**

2. Go to Menu (dots 3x3) > Integarations > Bot Accounts:
    - click **Add Bot Account**
    - set **Username** to "impulse"
    - optionally set [our logo](https://github.com/eslupmi/site/blob/develop/static/logo.png?raw=true) as the **Bot Icon**
    - set **Display Name** to "IMPulse"
    - set **Role** to "System Admin"
    - click **Create Bot Account**
    - copy the "Token" and use it as the `MATTERMOST_ACCESS_TOKEN` environment variable (see [step 2.3 here](installation.md#3-configure-impulse))
    - click **Done**

## Configure bot

1. Go to Menu (dots 3x3) > System Console > User Management > Teams:
    - press on your Team
    - press the button **Add Members**
    - type "impulse" in search, select it and press the button **Add**
    - press the button **Save**

## Configure channels

1. To use IMPulse bot in private channels you **must** add it manually. Run this command in all necessary private channels:

    ```
    /invite @impulse
    ```

2. Users listed in `application.admin_users` **must** be present in all channels defined in `route`.

3. Users mentioned in `application.chains` should be added to their respective channels.
    
    To simplify this, you can add all `application.users` to all channels from the `route` block.

4. We highly recommend configuring notification preferences for `application.users` in their `route` channels:
    - select the channel in main list and press on it
    - click the **View Info** icon (`i`) in the top right, click **Notifications Preferences**
    - in the "Notify me about..." choose "Mentions, direct messages, and keywords only"
    - click **Save**.
