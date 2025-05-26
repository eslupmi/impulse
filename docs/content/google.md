# Google Calendar

Google calendar can be used as [cloud chain](config_file.md#cloud-chain). To enable it, you need to create a Google Cloud Project and generate a service account key file `key.json` to use as [`GOOGLE_SERVICE_ACCOUNT_FILE`](envs.md).

## Create project and get key.json

1. Create google cloud project [here](https://console.cloud.google.com)
2. Navigate to "APIs & Services" and enable "Google Calendar API"
3. Open "Service Account", create a new service account
4. In the newly created service account, go to the "Keys", press "Add key" -> "Create new key" -> "JSON". The `key.json` file will be downloaded automatically
5. Move this file to the `GOOGLE_SERVICE_ACCOUNT_FILE` path (`./key.json` by default)

## Add you service account to a calendar

1. Go to created "Service Account" -> "Details"
2. Copy "Email", open calendar settings and share calendar with this email. Set "See all event details" permissions.
