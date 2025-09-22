# Configuration File

<style>
.md-typeset h2,
.md-typeset h3,
.md-typeset h4,
.md-typeset h5,
.md-typeset h6 {
  font-size: 1.0em;
  font-weight: 600;
  margin-top: 1.5em;
  margin-bottom: 0.75em;
  text-transform: none;
}  
</style>

> The only configuration file for IMPulse is `impulse.yml`. To change default `impulse.yml` path, see [Environment Variables](envs.md).

> [Here](https://github.com/eslupmi/impulse/tree/develop/examples) you can find examples of both minimal and advanced configuration files for all the messengers we support.

> - **minimal** — includes only the required fields to get started;
> - **advanced** — includes additional options with comments, serving as a reference example;

> Fields marked with "*" are mandatory within their parent section, but only if that parent section is present in the configuration.

> Below you'll see all the options supported by IMPulse.

## application *

- **description:** messenger configuration
- **type:** dict

### application.address * (Mattermost)

- **description:** your Mattermost server address
- **type:** string

### application.admin_users *

- **description:** IMPulse administrators (from `application.users`) notified of any warnings
- **type:** list

### application.channels *

- **description:** define channels by their ID to use them in the [route](#route) section. Use your messenger's UI to find the channel IDs.
- **type:** dict

> **Example**
> === "Slack"
>     ```yaml
>     application:
>       channels:
>         incidents_default: {id: C09NSUL269T}
>     ```
> 
> === "Mattermost"
>     ```yaml
>     application:
>       channels:
>         incidents_default: {id: w8gvebq58fgo9civ8begs6renw}
>     ```
> 
> === "Telegram"
>     ```yaml
>     application:
>       channels:
>         incidents_default: {id: -1003748296152}
>     ```

### application.chains

- **description:** defines notification order. See [details](#applicationchains)
- **type:** dict

> Chains define how to notify people about incidents. Chains are used in the [route](#route) section.

> Each chain contains a list of **steps**. There are 5 step types. 3 of them are notifications:

> - [`user`](#applicationusers)
> - [`user_group`](#applicationuser_groups)
> - [`webhook`](#webhooks)

> The fourth step type is `wait`, which delays the execution of the next notification. Its format is similar to the [sleep](https://www.gnu.org/software/coreutils/manual/html_node/sleep-invocation.html) utility format, but it does not support floats or combined expressions like `1m 3s`. Valid units: `s` (seconds), `m` (minutes), `h` (hours), `d` (days).

> The fifth step type is `chain`, which allows you to include [nested chains](#nested-chain) within a parent chain.

> There are 3 types of chain:

> - simple
> - schedule
> - cloud

#### &lt;simple chain&gt;

- **description:** a basic escalation chain. It starts executing when an incident is created.
- **type:** list

> **Example**:
> ```yaml
> # Defined two simple chains for DevOps team
> application:
>   chains:
>     devops:
>       - user: Dmitry
>       - wait: 5m
>       - user: Dmitry_s_boss
>     devops-critical:
>       - user: Dmitry
>       - wait: 3m
>       - webhook: Dmitry_call
>       - wait: 5m
>       - user: Dmitry_s_boss
>       - wait: 15m
>       - user: CTO
> ```

#### &lt;schedule chain&gt;

- **description:** a chain that allows you to define notification logic based on a calendar schedule.
- **type:** dict

> It is recommended to use `steps` without `matcher` at the end to handle unmatched datetimes.

> **Examples:**
> ```yaml
> application:
>   chains:
>     support:
>       type: schedule
>       timezone: Asia/Tashkent
>       schedule:
>         - matcher:
>             start_day_expr: dow
>             start_day_values: ["Mon", "Tue"]
>             start_time: "09:00" # 24h format
>             duration: 24h
>           steps:
>             - user: Dmitry
>         - matcher:
>             start_day_expr: dow
>             start_day_values: ["Wed", "Thu"]
>             start_time: "09:00" # 24h format
>             duration: 24h
>           steps:
>             - user: Alexander
>         - steps: # will work at Sunday
>             - user: Administrator
> ```
> 
> You can also use modulus expressions for `dow` and `dom`:
> 
> ```yaml
> - matcher:
>     start_day_expr: dow % 2
>     start_day_values: [0] # matches when Tue, Thu, Sat
> ```
> 
> ```yaml
> application:
>   chains:
>     support:
>       type: schedule
>       timezone: Asia/Tashkent
>       schedule:
>         - {matcher: {start_day_expr: dow, start_day_values: [1, 2], start_time: "12:00", duration: 12h}, steps: [{user: Dmitry}]}
>         - {matcher: {start_day_expr: dow, start_day_values: [3, 4], start_time: "12:00", duration: 12h}, steps: [{user: Alexander}]}
>         - {matcher: {start_day_expr: dow, start_day_values: [5, 6], start_time: "12:00", duration: 12h}, steps: [{user: Maria}]}
>         - {steps: [{user: Oleg }]} # full Sunday and 00:00 to 12:00 every day
> ```

##### application.chains[].type *

- **description:** set chain type using `type: schedule`
- **type:** string

##### application.chains[].timezone

- **description:** time zone in "TZ identifier" format (details [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#Time_zone_abbreviations))
- **type:** string
- **default value:** UTC

##### application.chains[].schedule

- **description:** list of matchers with corresponding steps. IMPulse evaluates matchers from top to bottom. If a `matcher` matches the current time, the corresponding `steps` defined for that `matcher` are selected.
- **type:** list

> **Examples:**
> ```yaml
> application:
>   chains:
>     support:
>       type: schedule
>       timezone: Asia/Tashkent
>       schedule:
>         - matcher:
>             start_day_expr: dow
>             start_day_values: ["Mon", "Tue"]
>             start_time: "09:00"
>             duration: 24h
>           steps:
>             - user: Dmitry
>         - steps:
>             - user: Administrator
> ```

> **matcher**

> - **description:** datetime matcher which will be compared with current datetime
> - **type:** dict
> 
> Matcher contains theese fields:
> > **start_day_expr** *
> >
> > - **description:** date matching strategy: "dow" (day of week), "dom" (day of month), "date" (exact date). Expressions like "dow % 2" (least positive remainder) are also allowed.
> > - **type:** string
> >
> > **start_day_values** *
> >
> > - **description:** values for the expression **start_day_expr**
> > - **type:** list
> >
> > > Available values:
> >
> > >   - for `dow`: 0 to 7 (like in [cron](https://en.wikipedia.org/wiki/Cron)) or "Sun", "Mon"...
> > >   - for `dom`: 1 to 31
> > >   - for `date`: "2024-12-24" format
> > 
> > **start_time**
> >
> > - **description:** local time in "HH:MM" format (24-hour)
> > - **type:** string
> > 
> > **duration**
> >
> > - **description:** duration of the active window, e.g., "12h" or "2d"
> > - **type:** string
> 
> **steps**

> - **description:** list of chain steps (same as in [simple chain](#simple-chain)). It is recommended to use `steps` without `matcher` at the end to handle unmatched datetimes.
> - **type:** list

#### &lt;cloud chain&gt;

- **description:** a chain that allows you to define dynamic chains using calendar providers (e.g., Google). Setup instruction [here](google.md).
- **type:** dict

> Special ENVs (see [details](envs.md)):

> - `CHAIN_PROVIDER_DAYS_TO_SYNC`
> - `CHAIN_PROVIDER_MAX_EVENTS`
> - `CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS`
> - `GOOGLE_SERVICE_ACCOUNT_FILE`

##### application.chains[].type *

- **description:** chain type
- **type:** string
- **options:**
    - `cloud` only

##### application.chains[].provider *

- **description:** cloud calendar provider
- **type:** string
- **options:**
    - `google` only

##### application.chains[].calendar_id *

- **description:** calendar ID. Get it on calendar settings page
- **type:** string

##### application.chains[].default_steps

- **description:** chain steps if there are no calendar events at the moment
- **type:** list

> To use cloud chains you should generate service account file `key.json` (see [instructions](google.md#create-project-and-get-keyjson) for google provider) and [add service account to your calendar](google.md#set-up-calendar-access-for-your-service-account).

> Create "Event" in calendar. Put chain steps in "Description" using format:

> ```yaml
> - user: Dmitry
> - wait: 10m
> - user: Maria
> ```
> 
> **Example**
> 
> With event in calendar
> 
> ```yaml
> name: Test event
> from: 2024-12-24 15:00 (Asia/Tashkent)
> to: 2024-12-25 15:00 (Asia/Tashkent)
> description:
>   - user: Valery
> ```
> 
> and config
> 
> ```yaml
> application:
>   chains:
>     devops:
>       type: cloud
>       provider: google
>       calendar_id: b7ec15a9f4cb22d45819b7d3e96424a03e51987461adbc22385f964cf7103a62@group.calendar.google.com
>       default_steps:
>         - user: Dmitry
>         - wait: 5m
>         - user: Maria
> ```
> 
> Under the hood, the following `schedule chain` will be generated:
> 
> ```yaml
> application:
>   chains:
>     devops:
>       type: schedule
>       timezone: Asia/Tashkent
>       schedule:
>         - {matcher: {start_day_expr: date, start_day_values: ["2024-12-24"], start_time: "15:00", duration: 24h}, steps: [{user: Valery}]}
>         - {steps: [{user: Dmitry}, {wait: 5m}, {user: Maria}]}
> ```

#### &lt;nested chain&gt;

- **description:** allows one chain to include other chains as nested steps
- **type:** string

> Additionally, the `chain` step can be used with all types of chains. This allows one chain to include other nested chains. In some cases, this approach simplifies and reduces the overall configuration. Nesting is supported to any depth.
> 
> **Example**
> 
> ```yaml
> application:
>   chains:
>     devops:
>       - user: Dmitry
>       - wait: 5m
>       - user: Dmitry_s_boss
>     programmers:
>       - user: Valery
>       - wait: 5m
>       - chain: devops
> ```

### application.impulse_address * (Mattermost, Telegram)

- **description:** URL for Mattermost / Telegram button callbacks
- **type:** string

### application.users *

- **description:** users declaration. Defines users used in [chains](#applicationchains) for direct notifications.
- **type:** dict

> See instructions for getting user `id` for Slack ([here](https://www.workast.com/help/article/how-to-find-a-slack-user-id/)), Mattermost ([here](https://docs.mattermost.com/configure/user-management-configuration-settings.html#identify-a-user-s-id)), Telegram ([here](telegram.md#configure-group)).

> **Example**

> === "Slack"
>     ```yaml
>     application:
>       users:
>         Dmitry: {id: U73MD1YLR4M}
>     ```

> === "Mattermost"
>     ```yaml
>     application:
>       users:
>         Dmitry: {id: ic8pft3ac7rjrd9eopxp4kc7qy}
>     ```

> === "Telegram"
>     ```yaml
>     application:
>       users:
>         Dmitry: {id: 482913726}
>     ```

### application.user_groups

- **description:** groups of users for bulk notification. Used in [chains](#applicationchains).
- **type:** list

> **Example**

> ```yaml
> application:
>   user_groups:
>     developers: {users: ["Dmitry", "Alexander"]}
> ```

### application.team * (Mattermost)

- **description:** Mattermost team name
- **type:** string

### application.template_files

- **description:** path to custom template files for `status_icons`, `header`, and `body` (see [Incident Structure](concepts.md#structure))
- **type:** dict

> IMPulse uses [jinja2 templates](https://pypi.org/project/Jinja2/) to set messages format. And you can modify it.

> Incident message contains three parts ([picture](concepts.md/#structure)). Default template files for theese parts is [here](https://github.com/DiTsi/impulse/tree/develop/templates). You can copy the default templates, modify them, and specify custom paths.

> Template files can contain special words `incident` and `payload` as variables to show additional info. `incident` contains [incident attributes](https://github.com/DiTsi/impulse/blob/v1.4.0/app/incident/incident.py#L21) (used [here](https://github.com/DiTsi/impulse/blob/develop/templates/slack_status_icons.j2#L1)). `payload` is an Alertmanager alerts payload

> **Example**

> ```yaml
> application:
>   template_files:
>     status_icons: ./templates/status_icons.yml
>     header: ./templates/header.yml
>     body: ./templates/body.yml
> ```

#### application.template_files.body

- **description:** path to the custom template file that defines the format of `body`
- **type:** string
- **default value:** ./templates/[&lt;application.type&gt;](#applicationtype)_body.j2

#### application.template_files.header

- **description:** path to the custom template file that defines the format of `header`
- **type:** string
- **default value:** ./templates/[&lt;application.type&gt;](#applicationtype)_header.j2

#### application.template_files.status_icons

- **description:** path to the custom template file that defines the format of `status_icons`
- **type:** string
- **default value:** ./templates/[&lt;application.type&gt;](#applicationtype)_status_icons.j2

### application.type *

- **description:** messenger type
- **type:** string
- **options:**
    - `slack` - Slack messenger
    - `mattermost` - Mattermost messenger
    - `telegram` - Telegram messenger
    - `none` - disable messenger integration

## incident

- **description:** incidents behavior options
- **type:** dict

### incident.notifications

- **description:** incident notifications settings
- **type:** dict

#### incident.notifications.assignment

- **description:** enable/disable notifications about incident assignment changes
- **type:** bool
- **default value:** True

#### incident.notifications.new_firing

- **description:** notification about new firing instances
- **type:** bool
- **default value:** True

#### incident.notifications.partial_resolved

- **description:** nofitication about some resolved instances
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

- **description:** incident routing rules based on alert fields. See [details](#route)
- **type:** dict

> Route configure messenger channels, where incidents will be created, and [chains](#applicationchains) to notify people by rules.

> It is very similar to Alertmanager's [route](https://prometheus.io/docs/alerting/latest/configuration/#route). But has only four instructions: `routes`, `matchers`, `channel`, `chain`.

> Matchers use Python regular expressions instead of Alertmanager's syntax.

> **Example**:
> ```yaml
> route:
>   channel: incidents_default # default channel where incidents will be created if their didn't match any matchers
>   chain: devops # optional, but we recommend set it to handle alerts didn't match any matchers
>   routes:
>     # Infrastructure routes
>     - matchers:
>         - service =~ "cpu|disk|memory|network" # regex selector powered by Python regex
>       channel: incidents-infrastructure # channel for not "critical" or "warning" severity
>       # no chain here means users will not be notified, just incident created
>       routes:
>         - matchers:
>             - severity = "critical" # simple selector
>           channel: incidents-infrastructure
>           chain: devops-critical
>         - matchers:
>             - severity = "warning"
>           channel: incidents-infrastructure
>           chain: devops
> 
>     # Services routes
>     - matchers:
>         - service = "fingernote"
>       channel: incidents-services
>       chain: fingernote-team
>       routes:
>         - matchers:
>             - severity = "critical"
>           channel: incidents-services
>           chain: fingernote-team-critical
>     - matchers:
>         - service = "pickcase"
>       channel: incidents-services
>       chain: pickcase-team
>       routes:
>         - matchers:
>             - severity = "critical"
>           channel: incidents-services
>           chain: pickcase-team-critical
> ```

### route.channel *

- **description:** default [channel](#applicationchannels) where incidents will be created if they don't match any matchers
- **type:** string

### route.chain

- **description:** default [chain](#applicationchains) to notify users if alert don't match any matchers inside [route.routes](#routeroutes)
- **type:** string

### route.routes

- **description:** list of routing rules based on matchers to determine which channel and chain to use for incidents
- **type:** list

#### route.routes[].matchers

- **description:** conditions to match alert fields using Python regex patterns
- **type:** list

#### route.routes[].channel

- **description:** [channel](#applicationchannels) where incidents will be created if they match the matchers
- **type:** string

#### route.routes[].chain

- **description:** [chain](#applicationchains) to notify users if incidents match the matchers
- **type:** string

#### route.routes[].routes

- **description:** nested routing rules for more detailed incident classification (recursive structure)
- **type:** list

## ui

- **description:** user interface configuration (see [details](ui.md)). The `ui:` block enables the web interface
- **type:** dict

> **Example**:
> 
> ```yaml
> ui:
>   columns:
>     - name: status
>       header: Status
>       value: incident.status
>     - name: created
>       type: datetime
>       header: Created
>       value: incident.created
>     - name: alertname
>       header: Alertname
>       type: link
>       url: incident.link
>       value: payload.commonLabels.alertname
>     - name: severity
>       header: Severity
>       value: payload.commonLabels.severity
>     - name: summary
>       header: Summary
>       value: payload.commonAnnotations.summary
>   colors:
>     severity:
>       critical: "#FF0000"
>       warning: "#FFA500"
>       info: "#00FF00"
>   filters:
>     - severity="critical"
>   sorting:
>     - severity: desc
>       order: ["info", "warning", "critical"]
>     - created: desc
> ```

### ui.colors

- **description:** allows you to color the border of a specific cell in a column based on its value.
- **type:** dict

> **Example**
> ```yaml
> ui:
>   colors:
>     severity: # column name
>       critical: "#FF0000" # set red border for column severity="critical"
>       warning: "#FFA500" # set orange border for column severity="warning"
>       info: "#00FFFF" # set cyan border for column severity="info"
>     team: # column name
>       devops: "#00FFFF" # set cyan border for column team="info"
> ```

### ui.columns *

- **description:** defines the columns that are used in the user interface
- **type:** list

#### ui.columns[].name *

- **description:** unique identifier for the column, used for filtering and sorting
- **type:** string

#### ui.columns[].header *

- **description:** display name shown in the column header
- **type:** string

#### ui.columns[].value *

- **description:** data source variable (e.g., `incident.status`, `payload.commonLabels.alertname`)
- **type:** string

> Two special keywords are used: `incident` and `payload`. `incident` refers to the incident object. You can see your incident objects at `http://localhost:5000/incidents`. `payload` is the last message sent by Alertmanager for this incident (`payload` corresponds to `incident.payload`)

#### ui.columns[].type

- **description:** column data type that determines how the value is rendered
- **type:** string
- **default value:** `string`
- **options:**
    - `string` - plain text
    - `datetime` - date/time values with [formatting options](#uicolumnsformat)
    - `link` - clickable links (requires [url](#uicolumnsurl) field)

#### ui.columns[].visible

- **description:** whether the column is visible by default in the UI. Invisible columns can be used in search fields.
- **type:** boolean
- **default value:** True

#### ui.columns[].url

- **description:** variable containing the required link (e.g., `incident.link`) (used with `type: link`)
- **type:** string

#### ui.columns[].format

- **description:** formatting option for datetime columns (used with `type: datetime`)
- **type:** string
- **default value:** relative
- **options:**
    - `absolute` - full date and time
    - `relative` - relative time (e.g., "2h ago")

> **Example**:
> 
> ```yaml
> ui:
>   columns:
>     - name: status
>       header: Status
>       type: string
>       value: incident.status
>       visible: True
>     - name: created
>       type: datetime
>       header: Created
>       value: incident.created
>     - name: alertname
>       header: Alertname
>       url: incident.link
>       value: payload.commonLabels.alertname
>     - name: severity
>       header: Severity
>       value: payload.commonLabels.severity
>     - name: summary
>       header: Summary
>       value: payload.commonAnnotations.summary
> ```

### ui.filters

- **description:** defines the default filters applied in the user interface
- **type:** list

> **Example**

> ```yaml
> ui:
>   filters:
>     - severity=~"warning|critical"
> ```

### ui.sorting

- **description:** the default column sorting order
- **type:** list

> Sorting contains a list of column names and their sorting methods. There are three sorting methods: **asc**, **desc**, and **none**:

> - **asc** sorts values in alphabetical order
> - **desc** sorts in reverse alphabetical order
> - **none** disables sorting by default and used to define a custom order

> Custom sorting is defined using the `order` field, which specifies the exact sequence in which rows should appear when `asc` is selected. If you want to disable sorting by default but use a custom order for some columns, use the `none` method.

> **Example:**

> ```yaml
> ui:
>   sorting:
>     - created: desc
>     - severity: none
>       order: ["info", "warning", "critical"]
> ```

## webhooks

- **description:** webhooks provide alternative notification options via HTTP POST requests to custom endpoints.
- **type:** dict

> Webhooks support variables:
> 
> - `env` - to get environment variables (e.g. passwords, tokens)
> - `incident` - to get current incident fields

> **Examples**

> Twilio.com calls

> *To make this configs works you should add theese custom [Environment Variables](envs.md)*:
>
> - TWILIO_ACCOUNT_SID
> - TWILIO_AUTH_TOKEN
> - TWILIO_NUMBER

> ```yaml
> webhooks:
>   Dmitry_call:
>     url: 'https://api.twilio.com/2010-04-01/Accounts/{{ env["TWILIO_ACCOUNT_SID"] }}/Calls.json'
>     data:
>       To: '+998xxxxxxxxx'
>       From: '{{ env["TWILIO_NUMBER"] }}'
>       Url: http://example.com/twiml.xml
>     auth: '{{ env["TWILIO_ACCOUNT_SID"] }}:{{ env["TWILIO_AUTH_TOKEN"] }}'
> ```
> 
> Zvonok.com calls
> 
> *To make this config works you should add theese custom [Environment Variables](envs.md)*:
> 
> - ZVONOK_CAMPAIGN_ID
> - ZVONOK_PUBLIC_KEY
> 
> ```yaml
> webhooks:
>   Dmitry_call:
>     url: "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
>     data:
>       campaign_id: '{{ env["ZVONOK_CAMPAIGN_ID"] }}'
>       phone: '+998xxxxxxxxx'
>       public_key: '{{ env["ZVONOK_PUBLIC_KEY"] }}'
> ```

### webhooks[].auth

- **description:** string for HTTP Basic Auth (e.g., user:password)
- **type:** string

### webhooks[].url *

- **description:** URL to which the HTTP POST request will be sent
- **type:** string

### webhooks[].data

- **description:** data to be sent in the POST request body
- **type:** dict
