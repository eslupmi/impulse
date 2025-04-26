# Google Calendar

Google calendar can be used as [cloud chain](config_file.md#cloud-chain). To use it you should create Google Cloud project and generate service accout file `key.json` to use as [`GOOGLE_SERVICE_ACCOUNT_FILE`](envs.md).

## Create project and get key.json

1. Create google cloud project [here](https://console.cloud.google.com)
2. Go to "APIs & Services" and enable "Google Calendar API"
3. Go to "Service Account", create a new one
4. In your new service accout go to "Keys", press "Add key" -> "Create new key" -> "JSON"
5. File with key will be automatically downloaded
6. Place it to `GOOGLE_SERVICE_ACCOUNT_FILE` path (`./key.json` by default)

## Add you service account to calendar

1. Go to created "Service Account" -> "Details"
2. Copy "Email", go to calendar settings and share calendar with this email. Set "See all event details" permissions.
