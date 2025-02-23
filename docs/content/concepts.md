# Concepts

IMPulse is installed between Alertmanager and one of the messengers.

![None](media/impulse.excalidraw.svg)

IMPulse gets alerts from Alertmanager and sends them to your messenger's channel based on `application` and `route` configuration (see [Configuration File](config_file.md)).

Alertmanager sends alerts with one of two statuses: **firing** and **resolved**. Of course, first status is always **firing** when problem occurs. Based on these statuses IMPulse creates Incidents.

<p align="center"><img src="../media/slack_firing.excalidraw.svg" alt="" width="400"/></p>

## Incident

Incident is a messege representation of alert with actual status.

### Structure
Starting from [`v1.0.0`](https://github.com/DiTsi/impulse/releases/tag/v1.0.0) incident messages have such structure:

<p align="center"><img src="../media/impulse_message_structure.excalidraw.svg" alt="" width="600"/></p>

Default templates for `status icons`, `header` and `body` are [here](https://github.com/DiTsi/impulse/tree/main/templates).

You can create your own template files based on defaults and set their path in [application.template_files](config_file.md).


### Statuses and their colors

Unlike of Alertmanager alerts, IMPulse Incidents may have 4 statuses: **firing**, **resolved**, **unknown**, **closed**.

#### firing and resolved

<img src="../media/slack_firing.excalidraw.svg" alt="" width="400"/> <img src="../media/slack_resolved.excalidraw.svg" alt="" width="400"/>

Incident changes status to **firing** and **resolved** based on Alertmanager's alerts statuses are sent to IMPulse.

#### unknown

<p align="center"><img src="../media/slack_unknown.excalidraw.svg" alt="" width="400"/></p>

IMPulse has additional status to determine incident status actuality.

Alertmanager has `repeat_interval` and `group_interval` values which force Alertmanager to send actual alert status even if it didn't change. 

IMPulse has [`incident.timeouts.firing`](config_file.md) option during which the incident status should be updated by Alertamanger.

For this you should set Alertmanager's `repeat_interval` + `group_interval` a little bit more than [`incident.timeouts.firing`](config_file.md).

If Incident status isn't updated during `incident.timeouts.firing` it switches to non-actual status named **unknown**.

The appearence of **unknown** Incident is caused by one of this reasons:

- IMPulse didn't receive actual status from Alertmanager. Maybe IMPulse was down, Alertmanager was down or there are some network problems
- `repeat_interval`+`group_interval` is less than IMPulse's `incident.timeouts.firing`

When Incident becomes **unknown** IMPulse sends warning message to `application.admin_users`.

#### closed

<p align="center"><img src="../media/slack_closed.excalidraw.svg" alt="" width="400"/></p>

It is an Incident which hasn't already been tracked by IMPulse. 

There are two ways how the Incident can be closed: 
- **resolved** Incident stays in this status for `incident.timeouts.resolved` time
- **unknown** Incidents stays in this status for `incident.timeouts.unknown` time


### Lifecycle

IMPulse creates an Incident with **firing** status and is  tracking it till the Incident status will become **closed**. 

Here you can see the whole lifecycle of an Incident:

![None](media/incident_behavior.excalidraw.svg)

Or individually for all statuses:

![None](media/incident_firing.excalidraw.svg)

![None](media/incident_unknown.excalidraw.svg)

![None](media/incident_resolved.excalidraw.svg)
