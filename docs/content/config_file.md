# Configuration File

The only configuration file for IMPulse is `impulse.yml`. To change default `impulse.yml` path see [Environment Variables](envs.md)


## All options

**incident** - incidents behavior options

> **alerts_firing_notifications** [`bool`, default `False`] - notification about new firing instances

> **alerts_resolved_notifications** [`bool`, default `False`] - nofitication about old resolved instances

> **timeouts** - incident status timeouts (to realize incident [lifecycle](concepts.md#lifecycle))

> > **firing** [`string`, default `6h`] - after this time Incident status will change from 'firing' to 'unknown' if no new alerts appear

> > **unknown** [`string`, default `6h`] - after this time Incident status will change from 'resolved' to 'closed' if no new alerts appear

> > **resolved** [`string`, default `12h`] - after this time Incident status will change from 'resolved' to 'closed' if no new alerts appear

**route** [`dict`, _required_] - route for incidents routing is based on alert's fields. See [details](config_file.md#route)

**application** [`dict`, _required_] - messenger configuration

> **address** [`string`, _mattermost only_] - your Mattermost server address

> **admin_users** [`list`, _required_] - IMPulse administrators. They will be notified when any warnings

> **impulse_address** [`string`] - define where Mattermost / Telegram will send button events

> **users** [`dict`, _required_] - users declaration. See [details](config_file.md#users)

> **user_groups** [`list`] - user groups declaration. See [details](config_file.md#user_groups)

> **channels** [`dict`, _required_] - messenger channels used in IMPulse. See [details](config_file.md#channels)

> **chains** [`dict`] - entity to describe notifications order. See [details](config_file.md#chains)

> **template_files** [`dict`] - path to custom template files. See [details](config_file.md#template_files)

> **type** [`string`, _required_] - type of messenger (`mattermost`, `slack` or `telegram`)

**webhooks** - see [details](config_file.md#webhooks) to understand how to work with it

**experimental** [`dict`] - experimental options (*WE HIGHLY RECOMMEND DO NOT USE IT*)

> **recreate_chain** [`bool`, default `False`] - this option will <!-- release incident --> enable chain and start it again when new alerts added to incident


## Details

### chains

Chain defines how to notify people about incident. Chains used in [route](config_file.md#route).

There are 3 types of chain: **simple**, **schedule** and **cloud**.

#### simple chain

Every chain has list of **steps**. Step can be one of 4 instructions. 3 of them is notifications: [`user`](config_file.md#users), [`user_group`](config_file.md#user_groups), [`webhook`](config_file.md#webhooks). The last one is `wait` - to split notifications by time.

`wait` format seems like [sleep](https://www.gnu.org/software/coreutils/manual/html_node/sleep-invocation.html) utility format, but without float support and complex expressions like `1m 3s`. Available 4 options: `s` (seconds), `m` (minutes), `h` (hours), `d` (days).

**devops chains example**

Defined two chains for DevOps team
```yaml
application:
  chains:
    devops:
      - user: Dmitry
      - wait: 5m
      - user: Dmitry_s_boss
    devops-critical:
      - user: Dmitry
      - wait: 3m
      - webhook: Dmitry_call
      - wait: 5m
      - user: Dmitry_s_boss
      - wait: 15m
      - user: CTO
```

#### schedule chain

Schedule chain add you ability to set chains with calendar

##### schedule chain options:

**type** [`string`, _required_] - set chain type using `type: schedule`

**timezone** [`string`, default `UTC`] - your timezone with "TZ identifier" format (details [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#Time_zone_abbreviations))

**schedule** [`list`] - list of datetime matchers with steps. Current datetime is compared with every matcher and if any matches, theese steps will be used

> **matcher** [`dict`] - datetime matcher which will be compared with current datetime

>> **start_day_expr** [`string`, _required_] - expression for start day. Available values: "dow" (day of week), "dom" (day of month), "date" (exactly date). Also you can use expressions like "dom % 2" for "dom" and "dow" which calculates least positive remainder as value.

>> **start_day_values** [`list`] - list of values for **start_day_expr**. Available values:

>>    - for `dow`: 0 to 7 (like in [cron](https://en.wikipedia.org/wiki/Cron)) or "Sun", "Mon"...

>>    - for `dom`: 1 to 31

>>    - for `date`: "2024.12.24" format

>> **start_time** [`string`] - local time when duty starts at start day

>> **duration** [`string`] - time range duration. Values format: "2d", "60m"...

> **steps** [`list`, _required_] - chain steps like in simple chain

We recommend to use `steps` without `matcher` in the end, to handle datetimes which don't match any of matchers.

**schedule chain examples**


```yaml
application:
  chains:
    support:
      type: schedule
      timezone: Asia/Tashkent
      schedule:
        - matcher:
            start_day_expr: dow
            start_day_values: ["Mon", "Tue"]
            start_time: "09:00" # 24h format
            duration: 24h # 0h..24h
          steps:
            - user: Dmitry
        - matcher:
            start_day_expr: dow
            start_day_values: ["Wed", "Thu"]
            start_time: "09:00" # 24h format
            duration: 24h # 0h..24h
          steps:
            - user: Alexander
        - steps: # will work at Sunday
            - user: Administrator
```

Also you can use this format for `dow` and `dom`:

```yaml
- matcher:
    start_day_expr: dow % 2
    start_day_values: [0] # matches when Tue, Thu, Sat
```

Defined two simple chains for DevOps team
```yaml
application:
  chains:
    support:
      type: schedule
      timezone: Asia/Tashkent
      schedule:
        - {matcher: {start_day_expr: dow, start_day_values: [1, 2], start_time: "12:00", duration: 12h}, steps: [{user: Dmitry}]}
        - {matcher: {start_day_expr: dow, start_day_values: [3, 4], start_time: "12:00", duration: 12h}, steps: [{user: Alexander}]}
        - {matcher: {start_day_expr: dow, start_day_values: [5, 6], start_time: "12:00", duration: 12h}, steps: [{user: Maria}]}
        - {steps: [{user: Oleg }]} # full Sunday and 00:00 to 12:00 every day
```

#### cloud chain

Cloud chain add you ability to set chains using cloud providers like Google.

Special ENVs: `CHAIN_PROVIDER_DAYS_TO_SYNC`, `CHAIN_PROVIDER_MAX_EVENTS`, `CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS`, `GOOGLE_SERVICE_ACCOUNT_FILE` (see [details](envs.md)).

##### cloud chain options:

**type** [`string`, _required_] - set chain type using `type: cloud`

**provider** [`string`, _required_] - cloud calendar provider. Available values: "google" only

**calendar_id** [`string`, _required_] - calendar ID. Get it on calendar settings page

**default_steps** [`list`] - chain steps if there are no calendar events at the moment

To use cloud chain you should generate service account file `key.json` (see [instructions](google.md#create-project-and-get-keyjson) for google provider) and [add service account to your calendar](google.md#add-you-service-account-to-calendar).

Create "Event" in calendar. Put chain steps in "Description" using format:

```yaml
- user: Dmitry
- wait: 10m
- user: Maria
```

**cloud chain example**

With event in calendar

```yaml
name: Test event
from: 2024.12.24 15:00 (Asia/Tashkent)
to: 2024.12.25 15:00 (Asia/Tashkent)
description:
  - user: Valery
```

and config

```yaml
application:
  chains:
    devops:
      type: cloud
      provider: google
      calendar_id: b7ec15a9f4cb22d45819b7d3e96424a03e51987461adbc22385f964cf7103a62@group.calendar.google.com
      default_steps:
        - user: Dmitry
        - wait: 5m
        - user: Maria
```

`schedule chain` like this will be generated under the hood:

```yaml
application:
  chains:
    devops:
      type: schedule
      timezone: Asia/Tashkent
      schedule:
        - {matcher: {start_day_expr: date, start_day_values: ["2024.12.24"], start_time: "15:00", duration: 24h}, steps: [{user: Valery}]}
        - {steps: [{user: Dmitry}, {wait: 5m}, {user: Maria}]}
```

### channels

Define channels with their ID for using in [route](config_file.md#route). Use your messanger UI to get channels ID

**channels examples**

Define default channels (Slack)
```yaml
application:
  channels:
    incidents_default: {id: C09NSUL269T}
```

Define default channel (Mattermost)
```yaml
application:
  channels:
    incidents_default: {id: w8gvebq58fgo9civ8begs6renw}
```

Define default channel (Telegram)
```yaml
application:
  channels:
    incidents_default: {id: -1003748296152}
```

### route

Route configure messenger channels, where incidents will be created, and [chains](config_file.md#chains) to notify people by rules.

It is very similar to Alertmanager's [route](https://prometheus.io/docs/alerting/latest/configuration/#route). But has only four instructions: `routes`, `matchers`, `channel`, `chain`.

Matchers work like Alertmanager's but use Python regex instead.

**route example**

Complex example with comments
```yaml
route:
  channel: incidents_default # default channel where incidents will be created if their didn't match any matchers
  chain: devops # optional, but we recommend set it to handle alerts didn't match any matchers
  routes:
    # Infrastructure routes
    - matchers:
        - service =~ "cpu|disk|memory|network" # regex selector powered by Python regex
      channel: incidents-infrastructure # channel for not "critical" or "warning" severity
      # no chain here means users will not be notified, just incident created
      routes:
        - matchers:
            - severity = "critical" # simple selector
          channel: incidents-infrastructure
          chain: devops-critical
        - matchers:
            - severity = "warning"
          channel: incidents-infrastructure
          chain: devops

    # Services routes
    - matchers:
        - service = "fingernote"
      channel: incidents-services
      chain: fingernote-team
      routes:
        - matchers:
            - severity = "critical"
          channel: incidents-services
          chain: fingernote-team-critical
    - matchers:
        - service = "pickcase"
      channel: incidents-services
      chain: pickcase-team
      routes:
        - matchers:
            - severity = "critical"
          channel: incidents-services
          chain: pickcase-team-critical
```

### template_files

IMPulse uses [jinja2 templates](https://pypi.org/project/Jinja2/) to set messages format. And you can modify it.

Incident message contains three parts ([picture](concepts.md/#structure)). Default template files for theese parts is [here](https://github.com/DiTsi/impulse/tree/develop/templates). Just copy, modify and replace default template files with yours.

Template files can contain special words `incident` and `payload` as variables to show additional info. `incident` contains [incident attributes](https://github.com/DiTsi/impulse/blob/v1.4.0/app/incident/incident.py#L21) (used [here](https://github.com/DiTsi/impulse/blob/develop/templates/slack_status_icons.j2#L1)). `payload` is an Alertmanager alerts payload

**template_files example**

```yaml
application:
  template_files:
    status_icons: ./templates/status_icons.yml # path to custom status_icons template file
    header: ./templates/header.yml # path to custom header template file
    body: ./templates/body.yml # path to custom body template file
```

### users

Object which define users. They used in [chains](config_file.md#chains) as one of notification type.

To get users `id` instructions for Slack ([here](https://www.workast.com/help/article/how-to-find-a-slack-user-id/)) and Mattermost ([here](https://docs.mattermost.com/configure/user-management-configuration-settings.html#identify-a-user-s-id)).

#### users example

**Slack example**

```yaml
application:
  users:
    Dmitry: {id: U73MD1YLR4M}
```

**Mattermost example**

```yaml
application:
  users:
    Dmitry: {id: ic8pft3ac7rjrd9eopxp4kc7qy}
```

### user_groups

Object to notify multiple users at once. They used in [chains](config_file.md#chains) as one of notification type.

#### user_groups example

```yaml
application:
  user_groups:
    developers: {users: ["Dmitry", "Alexander"]}
```

### webhooks

Webhooks is the only alternative notification way outside messenger. It used to send POST HTTP requests to any endpoint.

Webhooks can have special words `env` and `incident` as variables to use additional info:

- `env` to get environment variables, such as passwords and tokens. See examples below.
- `incident` to get current incident fields

#### webhooks examples

**Twilio.com calls**

```yaml
webhooks:
  Dmitry_call:
    url: 'https://api.twilio.com/2010-04-01/Accounts/{{ env["TWILIO_ACCOUNT_SID"] }}/Calls.json'
    data:
      To: '+998xxxxxxxxx'
      From: '{{ env["TWILIO_NUMBER"] }}'
      Url: http://example.com/twiml.xml
    auth: '{{ env["TWILIO_ACCOUNT_SID"] }}:{{ env["TWILIO_AUTH_TOKEN"] }}'
```

*To make this config works you should add theese custom [Environment Variables](envs.md)*
```ini
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_NUMBER
```

**Zvonok.com calls**

```yaml
webhooks:
  Dmitry_call:
    url: "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
    data:
      campaign_id: '{{ env["ZVONOK_CAMPAIGN_ID"] }}'
      phone: '+998xxxxxxxxx'
      public_key: '{{ env["ZVONOK_PUBLIC_KEY"] }}'
```

*To make this config works you should add theese custom [Environment Variables](envs.md)*

```ini
ZVONOK_CAMPAIGN_ID
ZVONOK_PUBLIC_KEY
```
