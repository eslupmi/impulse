# Incident

An incident is a message representation of an alert that displays the incident's current status. The status is shown using messenger entities like emojis or color bars. Notifications and events for this incident are sent to the message thread.

## Messages Structure

Incident messages have the following structure:
    
=== "Slack"

    <p align="center"><img src="../../media/impulse_slack_message_structure.excalidraw.svg" alt="" width="600"/></p>

=== "Mattermost"

    <p align="center"><img src="../../media/impulse_slack_message_structure.excalidraw.svg" alt="" width="600"/></p>

=== "Telegram"

    <p align="center"><img src="../../media/impulse_telegram_message_structure.excalidraw.svg" alt="" width="600"/></p>

Templates for **status icons**, **header** and **body** are [here](https://github.com/DiTsi/impulse/tree/develop/templates). See [details](templates.md).

### Buttons

Incidents in messengers have two mandatory buttons **Take It** (**Release**), **Freeze** and one optional button **Task**.

#### Take It (Release)

The button works differently depending on the incident's state.

By default, the button works as **Take It**. In this case it:

- stops chain escalation
- assigns (or reassigns) the incident to the user who clicked the button

The button turns into **Resolved** only when the incident is already associated with someone and is in the **resolved** status. In this case it:

- unassigns the incident
- resets the [chain](../config_file.md/#messengerchains)

#### Freeze
This is a time selector for choosing until when the incident will be [**frozen**](incident.md#frozen). The day and time for unfreezing are determined based on the [general.week_start](../config_file.md#generalweek_start) and [general.workday_start](../config_file.md#generalworkday_start) parameters. Timezone is set for each user [if available](messengers.md), otherwise it uses [general.timezone](../config_file.md#generaltimezone).

Freeze behaviour (if not [**frozen**](#frozen)):

- assigns the incident to the person who clicked the button (like [Take It](#take-it-release))
- stops activity on the incident (chain escalation, status updates)
- prevents creation of new incidents with the same identifier (like [silence](https://prometheus.io/docs/alerting/latest/alertmanager/#silences))
- displays the unfreeze datetime on the button instead of "Freeze"

Unfreeze behaviour (if [**frozen**](#frozen) with button):

- sets the actual incident status
- resumes activity on the incident (chain escalation, status updates)

#### Task

Button without text, only pin icon: 📌. Appears only if the [Task Management](../config_file.md#task_management) integration is configured.

**Behaviour**:

- creates a task in your [Task Management](../config_file.md#task_management) software
- the button disappears

## Statuses and their colors

Unlike Alertmanager alerts, IMPulse Incidents can have four statuses:

- **firing**
- **resolved**
- **unknown**
- **closed**

Incidents can also be temporarily **frozen**. This is a pseudo-status that hides the actual status and pauses further incident handling.

### **firing** and **resolved**

<img src="../../media/slack_firing.excalidraw.svg" alt="" width="400"/> <img src="../../media/slack_resolved.excalidraw.svg" alt="" width="400"/>

Incident status changes to **firing** and **resolved** based on Alertmanager's alert statuses received by IMPulse.

### **unknown**

<p align="center"><img src="../../media/slack_unknown.excalidraw.svg" alt="" width="400"/></p>

IMPulse introduces an additional status called **unknown** to indicate that the current status of the incident may be outdated.

Alert sources use **Group interval** and **Repeat interval** to periodically resend the current alert status, even if it hasn't changed. IMPulse has a setting [incident.timeouts.firing](../config_file.md#incidenttimeoutsfiring) which defines how long it should wait for an update from Alertmanager. If an Incident status isn't updated within [incident.timeouts.firing](../config_file.md#incidenttimeoutsfiring) it switches to non-actual status named **unknown**.

Possible causes of **unknown** status:

- IMPulse did not receive an updated alert status. Possible causes:
    - the alert was silenced
    - inhibited rules configured in Alertmanager were triggered ([fix it](../alertmanager.md#inhibition))
    - IMPulse or Alertmanager was down
    - network issues
- **Repeat Interval** + **Group Interval** in alert source less or equal IMPulse's [incident.timeouts.firing](../config_file.md#incidenttimeoutsfiring)

When an incident becomes **unknown** , IMPulse sends a warning message to `messenger.admin_users`[↰](../config_file.md#messengeradmin_users).

### **closed**

<p align="center"><img src="../../media/slack_closed.excalidraw.svg" alt="" width="400"/></p>

The **closed** status means the incident is **closed** and retained only for history and statistics. The retention period for a **closed** incident file is configured via `incident.timeouts.closed`[↰](../config_file.md#incidenttimeoutsclosed). You can see **closed** incidents in the UI by clicking the [archive button](ui.md#footer).

There are two ways an Incident can be closed:
- a **resolved** incident remains in that status for the duration of `incident.timeouts.resolved`[↰](../config_file.md#incidenttimeoutsresolved)
- an **unknown** incident remains in that status for the duration of `incident.timeouts.unknown`[↰](../config_file.md#incidenttimeoutsunknown)

### **frozen**

<p align="center"><img src="../../media/slack_frozen.excalidraw.svg" alt="" width="400"/></p>

The **frozen** state is a **pseudo-status** that temporarily pauses incident handling and suppresses status update. When an incident is **frozen**, its actual status (**firing**, **resolved**, **unknown**, or **closed**) is hidden but preserved underneath. Also, while the incident is **frozen**, no new incident with the same identifier will be created.

An incident can be **frozen** two ways:

- by clicking the [Freeze](#freeze) button and selecting a duration
- by [inhibition](inhibition.md), if the incident becomes a child

## Lifecycle

IMPulse creates an Incident with the **firing** status and tracks it until the incident is deleted (after `incident.timeouts.closed`[↰](#closed)).

Here is a visualization of the full incident lifecycle:

![None](../media/incident_behavior.excalidraw.svg)

Or individually by status:

![None](../media/incident_firing.excalidraw.svg)

![None](../media/incident_unknown.excalidraw.svg)

![None](../media/incident_resolved.excalidraw.svg)

![None](../media/incident_closed.excalidraw.svg)
