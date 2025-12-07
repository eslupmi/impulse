# Google Calendar [↰](../../config_file.md#cloud-chain)

Google Calendar can be used as a [cloud chain](../../config_file.md#cloud-chain). To enable it, you need to create a Google Cloud project and generate a service account key file named `key.json`, which will be used as [`GOOGLE_SERVICE_ACCOUNT_FILE`](../../envs.md).

## Create project and get key.json

1. Create a Google Cloud project [here](https://console.cloud.google.com)
2. Navigate to **"APIs & Services"** and enable **"Google Calendar API"**
3. Open **"Service Accounts"** and create a new service account
4. In the newly created service account, go to the **"Keys"** tab, click **Add key** > **Create new key** > **JSON**. The `key.json` file will be downloaded automatically
5. Move this file to the path specified in `GOOGLE_SERVICE_ACCOUNT_FILE` (`./key.json` by default)

## Set up calendar access for your service account

### For personal Google Cloud

1. Go to the created **Service Account** > **Details**
2. Copy the **Email**, open your calendar settings, and share the calendar with this email. Set permissions to **"See all event details"**

### For corporate Google Cloud (Google Workspace)

In the case of a corporate Google Cloud (Google Workspace), the calendar must be created by the service account. This is because you cannot grant **See all event details** permissions to a service account for an existing calendar owned by a regular user. Therefore, the calendar should be created by the service account, and then **owner** permissions should be granted to your user account.

Here is the code that creates such a calendar and grants you **owner** permissions: [link](../../code/google_create_calendar.py)

Download the script, replace the variables `SERVICE_ACCOUNT_FILE`, `USER_EMAIL_TO_SHARE_WITH`, `NEW_CALENDAR_SUMMARY`, `NEW_CALENDAR_DESCRIPTION`, `NEW_CALENDAR_TIMEZONE` with the appropriate values, and run it.
