## Mattermost

### Create bot

1. Go to Menu (dots 3x3) > System Console > Integrations > Bot Accounts:
    - set `True` for "Enable Bot Account Creation", press "Save"
2. Go to Menu (dots 3x3) > Integarations > Bot Accounts:
    - press the button "Add Bot Account"
    - type "impulse" to **Username**
    - you can set [our icon](https://github.com/eslupmi/site/blob/main/static/logo.png?raw=true) as **Bot Icon**
    - type "IMPulse" to **Display Name**
    - set **Role** to "System Admin"
    - press the button "Create Bot Account"
    - use "Token" as ENV `MATTERMOST_ACCESS_TOKEN` (use in 2.3 [here](installation.md#23-impulse))
    - press the button **Done**

### Configure bot

1. Go to Menu (dots 3x3) > System Console > User Management > Teams:
    - press on your Team
    - press the button **Add Members**
    - type "impulse" in search, select it and press the button **Add**
    - press the button **Save**

### Configure channels

1. To use IMPulse bot in private channels you **should** add it manually. Run command in all necessary private channels:

    ```
    /invite @impulse 
    ```

2. `application.admin_users` **should** be in all `route` channels.
3. Add users from `application.chains` to their channels.

    To make it simpler you can add all `application.users` to all channels from `route` block.

4. Highly recommend to set just mentions notifications for every of `application.users` for their `route` channels. Users on their channels should:
    - select channel in main list and press on it
    - press button **View Info** (symbol "i") on the right side, press **Notifications Preferences** button
    - in "Notify me about..." select "Mentions, direct messages, and keywords only"
    - press **Save**
