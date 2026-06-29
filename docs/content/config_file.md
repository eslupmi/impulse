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

IMPulse uses a single configuration file `impulse.yml`. You can customize its location using the `CONFIG_PATH`[↰](envs.md) environment variable.

The configuration can be [reloaded](concepts/check.md) while IMPulse is running without requiring a restart.
    
!!! info "Required fields"

    Fields marked with "*" are mandatory within their parent section, but only if that parent section is present in the configuration.

Below are all the configuration options supported by IMPulse.

## general

- **description:** general settings
- **type:** dict

### general.timezone

- **description:** default timezone (used for [Freeze](concepts/incident.md#freeze) delay)
- **type:** string 
- **default value:** UTC

### general.week_start

- **description:** first day of the week (used for [Freeze](concepts/incident.md#freeze) delay)
- **type:** string
- **default value:** Mon
- **allowed values:** 0 to 7 (like in [cron](https://en.wikipedia.org/wiki/Cron)) or "Sun", "Mon"...

### general.workday_start

- **description:** time when workday starts (used for [Freeze](concepts/incident.md#freeze) delay)
- **type:** string ("23:59" format)
- **default value:** "09:00"

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

- **description:** notification about new **firing** instances
- **type:** bool
- **default value:** True

#### incident.notifications.partial_resolved

- **description:** nofitication about some **resolved** instances
- **type:** bool
- **default value:** True

#### incident.notifications.status_update

- **description:** notifications about incident status updates
- **type:** bool
- **default value:** True

### incident.timeouts

- **description:** incident status timeouts (see [lifecycle](concepts/incident.md#lifecycle))
- **type:** dict

#### incident.timeouts.firing

- **description:** after this time, incident status changes from **firing** to **unknown** if no alerts appear
- **type:** string
- **default value:** 6h
- **allowed values:** `wait` instruction [format](config_file.md/#messengerchains)

#### incident.timeouts.unknown

- **description:** after this time, incident status changes from **unknown** to **closed** if no alerts appear
- **type:** string
- **default value:** 6h
- **allowed values:** `wait` instruction [format](config_file.md/#messengerchains)

#### incident.timeouts.resolved

- **description:** after this time, incident status changes from **resolved** to **closed** if no alerts appear
- **type:** string
- **default value:** 12h
- **allowed values:** `wait` instruction [format](config_file.md/#messengerchains)

#### incident.timeouts.closed

- **description:** after this time, **closed** incident will be deleted
- **type:** string
- **default value:** 90d
- **allowed values:** `wait` instruction [format](config_file.md/#messengerchains)

## inhibit_rules

- **description:** inhibition rules to suppress (freeze) target incidents when source incidents are active (see [concepts](concepts/inhibition.md))
- **type:** list
- **examples:**
    ```yaml
    inhibit_rules:
      # freeze 'warning' incidents when 'critical' incidents are in firing status
      # only applies to incidents with the same 'service' label
      - source_matchers:
          - severity = "critical"
        target_matchers:
          - severity = "warning"
        equal:
          - service
      # freeze 'info' incidents when 'warning' incidents are in firing status
      # only applies to incidents with the same 'service' label
      - source_matchers:
          - severity = "warning"
        target_matchers:
          - severity = "info"
        equal:
          - service
    ```

### &lt;rule&gt;.source_matchers

- **description:** list of matchers that identify source incidents (parent)
- **type:** list
- **allowed values:** route [matcher](#routematchers) syntax

### &lt;rule&gt;.target_matchers

- **description:** list of matchers that identify target incidents (childs)
- **type:** list
- **allowed values:** route [matcher](#routematchers) syntax

### &lt;rule&gt;.equal

- **description:** list of label names that must have equal values in both source and target incidents for inhibition to apply
- **type:** list
- **examples:**
    ```yaml
    equal:
      - service
    ```


## messenger *

- **description:** messenger configuration
- **type:** dict

### messenger.address *

- **impact:** `mattermost` only
- **description:** your messenger server address
- **type:** string

### messenger.admin_users *

- **description:** IMPulse administrators (from `messenger.users`[↰](#messengerusers)) notified of any warnings
- **type:** list

### messenger.channels *

- **description:** define channels by their ID to use them in the [route](#route) section. Use your messenger's UI to find the channel IDs.
- **type:** dict
- **examples:**

    === "Slack"
        ```yaml
        messenger:
          channels:
            incidents_default: {id: C09NSUL269T}
        ```

    === "Mattermost"
        ```yaml
        messenger:
          channels:
            incidents_default: {id: w8gvebq58fgo9civ8begs6renw}
        ```

    === "Telegram"
        ```yaml
        messenger:
          channels:
            incidents_default: {id: -1003748296152}
        ```

### messenger.chains

- **description:** escallation chains (policies) - notification sequences for incident escalation. Referenced in the [route](#route) section to determine which chains apply to which incidents.
- **type:** dict
- **details:**
    
    !!! note ""
        There are 3 chain types: [simple](#simple-chains), [schedule](#schedule-chains), [cloud](#cloud-chains). See their description below.

        **Steps**

        Each chain contains a list of **steps**. There are 6 step types:

        - `chain`[↰](#messengerchains)
        - `group`[↰](#messengergroups)
        - `user`[↰](#messengerusers)
        - `user_group`[↰](#messengeruser_groups)
        - `wait`
        - `webhook`[↰](#webhooks)

        `chain`[↰](#messengerchains) allows nesting any other chains. Nesting is supported to any depth.

        `wait`, which delays the execution of the next notification. Its format is similar to the [sleep](https://www.gnu.org/software/coreutils/manual/html_node/sleep-invocation.html) utility format, but it does not support floats or combined expressions like `1m 3s`. Valid units: `s` (seconds), `m` (minutes), `h` (hours), `d` (days).

- **examples:**

    ```yaml
    messenger:
      chains:
        programmers:
          - user: Valery
          - wait: 5m
          - chain: devops
        devops:
          - user: Dmitry
          - wait: 5m
          - user: Dmitry_s_boss
    ```

#### &lt;simple chains&gt;

- **description:** a basic escalation chain. It starts executing when an incident is created.
- **type:** list
- **examples:**

    ```yaml
    # Defined two simple chains for DevOps team
    messenger:
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

#### &lt;schedule chains&gt;

- **description:** a chain that allows you to define notification logic based on a calendar schedule.
- **type:** dict
- **examples:**

    ```yaml
    messenger:
      chains:
        support:
          type: schedule
          timezone: Asia/Tashkent
          schedule:
            - matcher:
                start_day_expr: dow
                start_day_values: ["Mon", "Tue"]
                start_time: "09:00" # 24h format
                duration: 24h
              steps:
                - user: Dmitry
            - matcher:
                start_day_expr: dow
                start_day_values: ["Wed", "Thu"]
                start_time: "09:00" # 24h format
                duration: 24h
              steps:
                - user: Alexander
            - steps: # will work at Sunday
                - user: Administrator
    ```

    You can also use modulus expressions for `dow` and `dom`:

    ```yaml
    - matcher:
        start_day_expr: dow % 2
        start_day_values: [0] # matches when Tue, Thu, Sat
    ```

    ```yaml
    messenger:
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

##### &lt;chain&gt;.type *

- **description:** chain type
- **type:** string
- **allowed values:** `schedule` for schedule chain

##### &lt;chain&gt;.timezone

- **description:** time zone in "TZ identifier" [format](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#Time_zone_abbreviations)
- **type:** string
- **default value:** UTC

##### &lt;chain&gt;.schedule

- **description:** list of matchers with corresponding steps
- **type:** list
- **details:**

    !!! note ""

        IMPulse evaluates matchers from top to bottom. If a `matcher` matches the current time, the corresponding `steps` defined for that `matcher` are selected
        
        **&lt;schedule&gt;.matcher**

        - **description:** datetime matcher which will be compared with current datetime
        - **type:** dict

        **&lt;schedule&gt;.matcher.start_day_expr** *
        
        - **description:** date matching strategy
        - **type:** string
        - **allowed values:**
            - "dow" - day of week
            - "dom" - day of month
            - "date" - exact date
            - "dow % 2" - least positive remainder (works with "dow", "dom")
        
        **&lt;schedule&gt;.matcher.start_day_values** *
        
        - **description:** values for the expression **start_day_expr**
        - **type:** list
        - **allowed values:**
            - for `dow`: 0 to 7 (like in [cron](https://en.wikipedia.org/wiki/Cron)) or "Sun", "Mon"...
            - for `dom`: 1 to 31
            - for `date`: "2024-12-24" format
        
        **&lt;schedule&gt;.matcher.start_time**
        
        - **description:** local time
        - **type:** string
        - **allowed values:** "HH:MM" format (24-hour)
        
        **&lt;schedule&gt;.matcher.duration**
        
        - **description:** duration of the active window
        - **type:** string
        - **allowed values:** `wait` instruction [format](config_file.md/#messengerchains)
        
        **&lt;schedule&gt;.steps** *

        - **description:** list of chain steps
        - **type:** list
        - **allowed values:** simple chain [format](#simple-chains)

- **examples:**

    ```yaml
    messenger:
      chains:
        support:
          type: schedule
          timezone: Asia/Tashkent
          schedule:
            - matcher:
                start_day_expr: dow
                start_day_values: ["Mon", "Tue"]
                start_time: "09:00"
                duration: 24h
              steps:
                - user: Dmitry
            - steps:
                - user: Administrator
    ```

#### &lt;cloud chains&gt;

- **description:** a chain that allows you to define dynamic chains using calendar providers (e.g., Google).
- **type:** dict
- **details:**
    
    !!! note ""
        **Configure**

        To use cloud chains you should generate service account file `key.json` (see [instructions](integrations/calendars/google.md#create-project-and-get-keyjson) for `google` provider) and [add service account to your calendar](integrations/calendars/google.md#set-up-calendar-access-for-your-service-account).

        Also you should set special [ENVs](envs.md):

        - `CHAIN_PROVIDER_DAYS_TO_SYNC`
        - `CHAIN_PROVIDER_MAX_EVENTS`
        - `CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS`
        - `GOOGLE_SERVICE_ACCOUNT_FILE`

        You can now create an Event in the calendar and add steps to the "Description" field using the standard format:

        ```yaml
        - user: Dmitry
        - wait: 10m
        - user: Maria
        ```

        The chain will trigger at the time specified in the Event. If no Event exists, the chain specified in `default_steps` will be used.

    **How it works**

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
    messenger:
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
    messenger:
      chains:
        devops:
          type: schedule
          timezone: Asia/Tashkent
          schedule:
            - {matcher: {start_day_expr: date, start_day_values: ["2024-12-24"], start_time: "15:00", duration: 24h}, steps: [{user: Valery}]}
            - {steps: [{user: Dmitry}, {wait: 5m}, {user: Maria}]}
    ```

##### &lt;chain&gt;.type *

- **description:** chain type
- **type:** string
- **allowed values:** `cloud` for cloud chain

##### &lt;chain&gt;.provider *

- **description:** cloud calendar provider
- **type:** string
- **allowed values:** `google` only ([setup instruction](integrations/calendars/google.md))

##### &lt;chain&gt;.calendar_id *

- **description:** calendar ID. Get it on calendar settings page
- **type:** string

##### &lt;chain&gt;.default_steps

- **description:** chain steps if there are no calendar events at the moment
- **type:** list
- **allowed values:** simple chain [format](#simple-chains)

#### &lt;ui chains&gt;

- **description:** a chain managed from the UI.
- **type:** dict
- **details:**
    
    !!! note ""
        Use UI chains for on-call rotations and quick shift updates without editing the config file.

        A UI chain is declared in config and edited from the **ui chains** button in the web interface (see [Footer](concepts/ui.md#footer)).

##### &lt;chain&gt;.type *

- **description:** chain type
- **type:** string
- **allowed values:** `ui` for UI-managed chain

- **examples:**

    ```yaml
    messenger:
      chains:
        oncall:
          type: ui
    ```

### messenger.groups

- **impact:** `mattermost`, `slack` only
- **description:** Messenger groups
- **type:** dict
- **details:**
    
    !!! note ""
        Instructions how to get groups `id`: [Slack](integrations/messengers/slack.md#get-group-id), [Mattermost](integrations/messengers/mattermost.md#get-group-ids)

- **examples:**

    === "Slack"
        ```yaml
        messenger:
          groups:
            devops_group: {id: S0A6WIL2F7T}
        ```

    === "Mattermost"
        ```yaml
        messenger:
          groups:
            devops_group: {id: ic8pft3ac7rjrd9eopxp4kc7qy}
        ```

### messenger.impulse_address *

- **impact:** `mattermost`, `telegram` only
- **description:** IMPulse address for button callbacks. Telegram supported only HTTPS.
- **type:** string

### messenger.users *

- **description:** users declaration. Defines users used in [chains](#messengerchains) for direct notifications.
- **type:** dict
- **details:**
    
    !!! note ""
        Instructions how to find users `id`: [Slack](./integrations/messengers/slack.md#get-user-id), [Mattermost](./integrations/messengers/mattermost.md#get-user-id), [Telegram](./integrations/messengers/telegram.md#get-user-id)

- **examples:**

    === "Slack"
        ```yaml
        messenger:
          users:
            Dmitry: {id: U73MD1YLR4M}
        ```

    === "Mattermost"
        ```yaml
        messenger:
          users:
            Dmitry: {id: ic8pft3ac7rjrd9eopxp4kc7qy}
        ```

    === "Telegram"
        ```yaml
        messenger:
          users:
            Dmitry: {id: 482913726}
        ```

### messenger.user_groups

- **description:** groups of users for bulk notification. Used in [chains](#messengerchains).
- **type:** list
- **examples:**

    ```yaml
    messenger:
      user_groups:
        developers: {users: ["Dmitry", "Alexander"]}
    ```

### messenger.team *

- **impact:** `mattermost` only
- **description:** team name
- **type:** string

### messenger.template_files

- **description:** path to custom template files for `status_icons`, `header`, and `body` (see [Incident Structure](concepts/incident.md#messages-structure))
- **type:** dict
- **[special variables](concepts/special_variables.md):** `incident`, `incidents` and `payload` supported
- **details:**
    
    !!! note ""
        IMPulse uses [jinja2 templates](https://pypi.org/project/Jinja2/) to set messages format. And you can modify it.

        Incident message contains three parts ([picture](concepts/incident.md#messages-structure)). Default template files for theese parts is [here](https://github.com/DiTsi/impulse/tree/develop/templates). You can copy the default templates, modify them, and specify custom paths.

- **examples:**

    ```yaml
    messenger:
      template_files:
        status_icons: ./templates/status_icons.yml
        header: ./templates/header.yml
        body: ./templates/body.yml
    ```

#### messenger.template_files.body

- **description:** path to the custom template file that defines the format of `body`
- **type:** string
- **default value:** `./templates/<messenger.type>_body.j2`

#### messenger.template_files.header

- **description:** path to the custom template file that defines the format of `header`
- **type:** string
- **default value:** `./templates/<messenger.type>_header.j2`

#### messenger.template_files.status_icons

- **description:** path to the custom template file that defines the format of `status_icons`
- **type:** string
- **default value:** `./templates/<messenger.type>_status_icons.j2`

### messenger.type *

- **description:** messenger type
- **type:** string
- **allowed values:**
    - `slack` - Slack messenger
    - `mattermost` - Mattermost messenger
    - `telegram` - Telegram messenger
    - `none` - disable messenger integration

## route *

- **description:** incident routing rules based on alert fields
- **type:** dict
- **details:**

    !!! note ""
        Route configure messenger channels, where incidents will be created, and [chains](#messengerchains) to notify people by rules.

        It is very similar to Alertmanager's [route](https://prometheus.io/docs/alerting/latest/configuration/#route). But has only four instructions: `routes`[↰](#routeroutes), `matchers`[↰](#routematchers), `channel`[↰](#messengerchannels), `chain`[↰](#messengerchains).

        Matchers use Python regular expressions instead of Alertmanager's syntax.

- **examples:**
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

### route.channel *

- **description:** default [channel](#messengerchannels) where incidents will be created if they don't match any matchers
- **type:** string

### route.chain

- **description:** default [chain](#messengerchains) to notify users if alert don't match any matchers inside [route.routes](#routeroutes)
- **type:** string

### route.routes

- **description:** list of routing rules based on matchers to determine which channel and chain to use for incidents
- **type:** list

#### &lt;route&gt;.matchers

- **description:** conditions to match alert fields using Python regex patterns
- **type:** list
- **allowed values:** same as Alertmanager's [matcher](https://prometheus.io/docs/alerting/latest/configuration/#matcher)

#### &lt;route&gt;.channel

- **description:** [channel](#messengerchannels) where incidents will be created if they match the matchers
- **type:** string

#### &lt;route&gt;.chain

- **description:** [chain](#messengerchains) to notify users if incidents match the matchers
- **type:** string

#### &lt;route&gt;.routes

- **description:** nested routing rules for more detailed incident classification (recursive structure)
- **type:** list

## task_management

- **description:** task tracking system integration configuration (e.g., Jira). The `task_management:` block enables [**Task**](concepts/incident.md#task) button.
- **type:** dict

### task_management.type *

- **description:** task tracking system type
- **type:** string
- **allowed values:** `jira` only - Jira integration (see [integration](integrations/task_management/jira.md))

### task_management.project_key *

- **description:** project key in the task tracking system where tasks will be created
- **type:** string
- **examples:**

    ```yaml
    task_management:
      type: jira
      project_key: PROJ
    ```

### task_management.template_files

- **description:** path to custom template files for task creation
- **type:** dict
- **[special variables](concepts/special_variables.md):** `incident` supported
- **details:**
    
    !!! note ""
        IMPulse uses [Jinja](https://pypi.org/project/Jinja2/) templates to format task summary and description. You can customize these templates to match your requirements.

- **examples:**

    ```yaml
    # Custom templates for both summary and description
    task_management:
      type: jira
      project_key: PROJ
      template_files:
        summary: templates/jira_custom_summary.j2
        description: templates/jira_custom_description.j2
    ```

#### task_management.template_files.summary

- **description:** path to the custom template file that defines the format of task summary
- **type:** string
- **default value:** `./templates/<task_management.type>_summary.j2`

#### task_management.template_files.description

- **description:** path to the custom template file that defines the format of task description
- **type:** string
- **default value:** `./templates/<task_management.type>_description.j2`

## ui

- **description:** user interface configuration (see [concepts](concepts/ui.md)). The `ui:` block enables the web interface
- **type:** dict
- **examples:**

    ```yaml
    ui:
      columns:
        - name: status
          header: Status
          value: incident.status
        - name: created
          type: datetime
          header: Created
          value: incident.created
        - name: alertname
          header: Alertname
          type: link
          url: incident.link
          value: payload.commonLabels.alertname
        - name: severity
          header: Severity
          value: payload.commonLabels.severity
        - name: summary
          header: Summary
          value: payload.commonAnnotations.summary
      colors:
        severity:
          critical: "#FF0000"
          warning: "#FFA500"
          info: "#00FF00"
      filters:
        - severity="critical"
      sorting:
        - severity: desc
          order: ["info", "warning", "critical"]
        - created: desc
    ```

### ui.colors

- **description:** allows you to color the border of a specific cell in a column based on its value.
- **type:** dict
- **examples:**

    ```yaml
    ui:
      colors:
        severity: # column name
          critical: "#FF0000" # set red border for column severity="critical"
          warning: "#FFA500" # set orange border for column severity="warning"
          info: "#00FFFF" # set cyan border for column severity="info"
        team: # column name
          devops: "#00FFFF" # set cyan border for column team="info"
    ```

### ui.columns *

- **description:** defines the columns that are used in the user interface
- **type:** list

#### &lt;column&gt;.name *

- **description:** unique identifier for the column, used for filtering and sorting
- **type:** string

#### &lt;column&gt;.header *

- **description:** display name shown in the column header
- **type:** string

#### &lt;column&gt;.value *

- **description:** data source variable (e.g., `incident.status`, `payload.commonLabels.alertname`)
- **type:** string
- **[special variables](concepts/special_variables.md):** `incident` and `payload` supported

#### &lt;column&gt;.type

- **description:** column data type that determines how the value is rendered
- **type:** string
- **default value:** `string`
- **allowed values:**
    - `string` - plain text
    - `datetime` - date/time values with [formatting options](#columnformat)
    - `link` - clickable links (requires [url](#columnurl) field)

#### &lt;column&gt;.visible

- **description:** whether the column is visible by default in the UI. Invisible columns can be used in search fields.
- **type:** boolean
- **default value:** True

#### &lt;column&gt;.url


- **description:** variable containing the required link (e.g., `incident.link`) (used with `type: link`)
- **type:** string
- **[special variables](concepts/special_variables.md):** `env` and `incident` supported

#### &lt;column&gt;.format

- **description:** formatting option for datetime columns (used with `type: datetime`)
- **type:** string
- **default value:** relative
- **allowed values:**
    - `absolute` - full date and time
    - `relative` - relative time (e.g., "2h ago")

- **examples:**

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

### ui.filters

- **description:** defines the default filters applied in the user interface
- **type:** list
- **examples:**

    ```yaml
    ui:
      filters:
        - severity=~"warning|critical"
    ```

### ui.sorting

- **description:** the default column sorting order
- **type:** list
- **details:**
    
    !!! note ""
        Sorting contains a list of column names and their sorting methods. There are three sorting methods:

        - `asc` sorts values in alphabetical order
        - `desc` sorts in reverse alphabetical order
        - `none` disables sorting by default. Used to define a custom order

        Custom sorting is defined using the `order` field, which specifies the exact sequence in which rows should appear when `asc` is selected. If you want to disable sorting by default but enable custom sorting on button click, use the `none` method.

- **examples:**

    ```yaml
    ui:
      sorting:
        - created: desc
        - severity: none
          order: ["info", "warning", "critical"]
    ```

## webhooks

- **description:** webhooks provide alternative notification options via HTTP POST requests to custom endpoints. See menu **INTEGRATIONS / External Notifications** menu for provider examples.
- **type:** dict

### &lt;webhook&gt;.auth

- **description:** string for HTTP Basic Auth (e.g., user:password)
- **type:** string
- **[special variables](concepts/special_variables.md):** `env` supported

### &lt;webhook&gt;.data

- **description:** data to be sent in the POST request body
- **type:** dict
- **[special variables](concepts/special_variables.md):** `env` and `incident` supported
- **details:** cannot be used together with `<webhook>.json`
- **examples:**

    ```yaml
    webhooks:
      dmitry_call:
        url: 'http://internal_system:8080'
        data:
          channel_id: '{{ incident["channel_id"] }}'

      complex_jinja_example:
        url: http://internal_system:8081/
        data:
          instances: '{{ incident.payload.alerts | map(attribute="labels.instance") | unique | join(", ") }}'
    ```

### &lt;webhook&gt;.json

- **description:** JSON data to be sent in the POST request body
- **type:** dict or str
- **[special variables](concepts/special_variables.md):** `env` and `incident` supported
- **details:** cannot be used together with `<webhook>.data`
- **examples:**

    ```yaml
    # Send alert payload
    webhooks:
      send_payload:
        url: 'http://another_host:5003/'
        json: '{{ incident["payload"] }}'
    ```

    ```yaml
    # Create custom JSON
    webhooks:
      generate_json:
        url: 'http://another_host:5003/'
        json:
          channel:
            id: '{{ incident["channel_id"] }}'
          status: '{{ incident["status"] }}'
    ```

### &lt;webhook&gt;.url *

- **description:** URL to which the HTTP POST request will be sent
- **type:** string
- **[special variables](concepts/special_variables.md):** `env` supported
