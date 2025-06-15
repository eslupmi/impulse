<!-- <link rel="stylesheet" href="link/to/stylesheet" /> -->
<style>
.md-typeset h2,
.md-typeset h3,
.md-typeset h4 {
  font-size: 1.0em;
  font-weight: 600;
  margin-top: 1.5em;
  margin-bottom: 0.75em;
}  
</style>

# Configuration File

The only configuration file for IMPulse is `impulse.yml`. To change default `impulse.yml` path, see [Environment Variables](envs.md)

Fields marked with "*" are mandatory within their parent section, but only if that parent section is present in the configuration.

## incident

- **description:** incidents behavior options
- **type:** dict

### incident.alerts_firing_notifications

- **description:** notification about new firing instances
- **type:** bool
- **default value:** False

### incident.alerts_resolved_notifications

- **description:** nofitication about old resolved instances
- **type:** bool
- **default value:** False

### incident.timeouts

- **description:** incident status timeouts (see [lifecycle](concepts.md#lifecycle))
- **type:** dict

#### incident.timeouts.firing

- **description:** after this time, incident status changes from 'firing' to 'unknown' if no alerts appear
- **type:** string
- **default value:** 6h

#### incident.timeouts.unknown

- **description:** after this time, incident status changes from 'unknown' to 'closed' if no alerts appear
- **type:** string
- **default value:** 6h

#### incident.timeouts.resolved

- **description:** after this time, incident status changes from 'resolved' to 'closed' if no alerts appear
- **type:** string
- **default value:** 12h

## route *

- **description:** incident routing rules based on alert fields. See [details](config_file.md#route)
- **type:** dict

Route configure messenger channels, where incidents will be created, and [chains](config_file.md#chains) to notify people by rules.

It is very similar to Alertmanager's [route](https://prometheus.io/docs/alerting/latest/configuration/#route). But has only four instructions: `routes`, `matchers`, `channel`, `chain`.

Matchers use Python regular expressions instead of Alertmanager's syntax.

<!-- ### route.channel *

- **description:** 
- **type:** dict

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

...

 -->

## application *

- **description:** messenger configuration
- **type:** dict

### application.address

- **description:** your Mattermost server address
- **type:** string

### application.admin_users *

- **description:** IMPulse administrators (from `application.users`) notified of any warnings
- **type:** list

### application.impulse_address

- **description:** URL for Mattermost / Telegram button callbacks
- **type:** string

### application.users *

- **description:** users declaration
- **type:** dict

Defines users used in [chains](config_file.md#chains) and for direct notifications.

See instructions for getting user `id` for Slack ([here](https://www.workast.com/help/article/how-to-find-a-slack-user-id/)) and Mattermost ([here](https://docs.mattermost.com/configure/user-management-configuration-settings.html#identify-a-user-s-id)).

**users example**

Slack example
```yaml
application:
  users:
    Dmitry: {id: U73MD1YLR4M}
```

Mattermost example
```yaml
application:
  users:
    Dmitry: {id: ic8pft3ac7rjrd9eopxp4kc7qy}
```

### application.user_groups

- **description:** user group definitions.
- **type:** list

Defines groups of users for bulk notification. Used in [chains](config_file.md#chains).

**user_groups example**

```yaml
application:
  user_groups:
    developers: {users: ["Dmitry", "Alexander"]}
```

### application.channels *

- **description:** messenger channels used in IMPulse.
- **type:** dict

Define channels by their ID to use them in the [route](config_file.md#route) section. Use your messenger's UI to find the channel IDs.

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

### application.chains

- **description:** defines notification order. See [details](config_file.md#chains)
- **type:** dict

Chains define how to notify people about incidents. Chains are used in the [route](config_file.md#route) section.

There are 3 types of chain:

- simple
- schedule
- cloud

Each chain contains a list of **steps**. There are 5 step types. 3 of them are notifications:

- [`user`](#applicationusers)
- [`user_group`](#applicationuser_groups)
- [`webhook`](#webhooks)

The fourth step type is `wait`, which delays the execution of the next notification. Its format is similar to the [sleep](https://www.gnu.org/software/coreutils/manual/html_node/sleep-invocation.html) utility format, but it does not support floats or combined expressions like `1m 3s`. Valid units: `s` (seconds), `m` (minutes), `h` (hours), `d` (days).

The fifth step type is `chain`, which allows you to include [nested chains](#nested-chain) within a parent chain.

#### simple chain

- **description:** 
- **type:** list

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

- **description:** schedule chains allows you to define notification chains based on a calendar
- **type:** dict

**type** [`string`, _required_] - set chain type using `type: schedule`

**timezone** [`string`, default `UTC`] - time zone in "TZ identifier" format (details [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#Time_zone_abbreviations))

**schedule** [`list`] - list of matchers with corresponding steps

> **matcher** [`dict`] - datetime matcher which will be compared with current datetime

>> **start_day_expr** [`string`, _required_] - date matching strategy: "dow" (day of week), "dom" (day of month), "date" (exact date). Expressions like "dow % 2" (least positive remainder) are also allowed.

>> **start_day_values** [`list`] - values for the expression **start_day_expr**. Available values:

>>    - for `dow`: 0 to 7 (like in [cron](https://en.wikipedia.org/wiki/Cron)) or "Sun", "Mon"...

>>    - for `dom`: 1 to 31

>>    - for `date`: "2024-12-24" format

>> **start_time** [`string`] - local time in "HH:MM" format (24h)

>> **duration** [`string`] - duration of the active window, e.g., "12h" or "2d"

> **steps** [`list`, _required_] - list of chain steps (same as in simple chain).

 It is recommended to use `steps` without `matcher` at the end to handle unmatched datetimes.

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

You can also use modulus expressions: `dow` and `dom`:

```yaml
- matcher:
    start_day_expr: dow % 2
    start_day_values: [0] # matches when Tue, Thu, Sat
```

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

Cloud chains allow you to configure dynamic chains using calendar providers (e.g., Google).

Special ENVs: `CHAIN_PROVIDER_DAYS_TO_SYNC`, `CHAIN_PROVIDER_MAX_EVENTS`, `CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS`, `GOOGLE_SERVICE_ACCOUNT_FILE` (see [details](envs.md)).

##### cloud chain options:

**type** [`string`, _required_] - set chain type using `type: cloud`

**provider** [`string`, _required_] - cloud calendar provider. Available values: "google" only

**calendar_id** [`string`, _required_] - calendar ID. Get it on calendar settings page

**default_steps** [`list`] - chain steps if there are no calendar events at the moment

To use cloud chains you should generate service account file `key.json` (see [instructions](google.md#create-project-and-get-keyjson) for google provider) and [add service account to your calendar](google.md#add-you-service-account-to-calendar).

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
from: 2024-12-24 15:00 (Asia/Tashkent)
to: 2024-12-25 15:00 (Asia/Tashkent)
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

Under the hood, the following `schedule chain` will be generated:

```yaml
application:
  chains:
    devops:
      type: schedule
      timezone: Asia/Tashkent
      schedule:
        - {matcher: {start_day_expr: date, start_day_values: ["2024-12-24"], start_time: "15:00", duration: 24h}, steps: [{user: Valery}]}
        - {steps: [{user: Dmitry}, {wait: 5m}, {user: Maria}]}
```

#### nested chain

Additionally, the `chain` step can be used with all types of chains. This allows one chain to include other nested chains. In some cases, this approach simplifies and reduces the overall configuration. Nesting is supported to any depth.

**nested chain example**

```yaml
application:
  chains:
    devops:
      - user: Dmitry
      - wait: 5m
      - user: Dmitry_s_boss
    programmers:
      - user: Valery
      - wait: 5m
      - chain: devops
```

> **team** [`string`, _required_] - Mattermost team name

> **template_files** [`dict`] - paths to custom template files. See [details](config_file.md#template_files)

> **type** [`string`, _required_] - messenger type (`mattermost`, `slack` or `telegram`)

**ui** [`dict`] - UI configuration. See [details](config_file.md#ui)

> **filters** [`list`] - default incidents filters. See [details](config_file.md#uifilters)

> **columns** [`list`] - enabled columns. See [details](config_file.md#uicolumns)

> **sorting** [`list`] - default sorting order. See [details](config_file.md#uisorting)

> **colors** [`dict`] - custom border color for columns. See [details](config_file.md#uicolors)

**webhooks** - see [details](config_file.md#webhooks) for usage instructions

**experimental** [`dict`] - experimental options (*WE HIGHLY RECOMMEND DO NOT USE IT*)

> **recreate_chain** [`bool`, default `False`] - enables the chain and restarts it when new alerts are added to an incident


## Details

### template_files

IMPulse uses [jinja2 templates](https://pypi.org/project/Jinja2/) to set messages format. And you can modify it.

Incident message contains three parts ([picture](concepts.md/#structure)). Default template files for theese parts is [here](https://github.com/DiTsi/impulse/tree/develop/templates). You can copy the default templates, modify them, and specify custom paths.

Template files can contain special words `incident` and `payload` as variables to show additional info. `incident` contains [incident attributes](https://github.com/DiTsi/impulse/blob/v1.4.0/app/incident/incident.py#L21) (used [here](https://github.com/DiTsi/impulse/blob/develop/templates/slack_status_icons.j2#L1)). `payload` is an Alertmanager alerts payload

**template_files example**

```yaml
application:
  template_files:
    status_icons: ./templates/status_icons.yml # path to custom status_icons template file
    header: ./templates/header.yml # path to custom header template file
    body: ./templates/body.yml # path to custom body template file
```

### ui.filters

### ui.columns

Columns enabled in UI

Every column must contain two fields: `name` and `value`. Using `name` you can filter 

There are 3 types of columns: `string` (default), `datetime`, `link`.

Set `type: string` to show any text information. `type: datetime` used for datetime fields as `incident.created`

```yaml
ui:
  columns:
    - name: status
      header: Status
      type: string
      value: incident.status
      visible: True
    - name: created
      type: datetime
      header: Created
      # format: absolute
      value: incident.created
    - name: alertname
      header: Alertname
      url: incident.link
      value: payload.commonLabels.alertname
    - name: severity
      header: Severity
      value: payload.commonLabels.severity
    - name: summary
      header: Summary
      value: payload.commonAnnotations.summary
```

### ui.sorting

### ui.colors


### webhooks

Webhooks provide alternative notification options via HTTP POST requests to custom endpoints.

Webhooks support variables:

- `env` - to get environment variables (e.g. passwords, tokens)
- `incident` - to get current incident fields

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
