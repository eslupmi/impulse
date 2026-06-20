# Changelog

## v3.6.0
Changes:
- Filters became editable
- UI update
- Added browser timezone for UI Chains and Maintenance

## v3.5.1
Changes:
- [Mattermost] Added workaround for links rendering bug on mobile

## v3.5.0
Changes:
- Added support for messenger [authentication](https://docs.impulse.bot/stable/guides/authentication/)
- Added standard incident action buttons to the UI
- Added support for [UI chains](https://docs.impulse.bot/stable/config_file/#ui-chains)
- Added the `/-/reload` endpoint for configuration reload
- [Mattermost] Updated header and body templates
- Removed buttons for closed incidents
- Fixed bugs

## v3.4.1
Changes:
- [_Slack_, _Mattermost_] Fixed assignment notification [bug](https://github.com/eslupmi/impulse/issues/428)

## v3.4.0
Changes:
- [Inhibition](https://docs.impulse.bot/stable/concepts/inhibition/) mechanism to suppress child Incidents
- [_Slack_, _Mattermost_] Added [support](https://docs.impulse.bot/stable/config_file/#messengergroups) for custom user groups

    ```bash
    # For Slack add `usergroups:read` permission
    ```

- [_Slack_, _Mattermost_] [Freeze](https://docs.impulse.bot/stable/concepts/buttons/#freeze) prefer User's timezone instead of [general](https://docs.impulse.bot/stable/config_file/#generaltimezone)
- [_Telegram_] Using new [colored buttons](https://t.me/telegram/427) feature for **Take It** button
- Added **Filter Out** button to UI
- Switch to **JSON** logs
- Added Jira task link to UI
- Moved Helm to [new repo](https://github.com/eslupmi-community/helm-charts) in community organization

    ```bash
    # Switch to community repo with commands:
    helm repo remove impulse
    helm repo add impulse https://eslupmi-community.github.io/helm-charts
    ```
- Fixed concurrent execution of multiple chain steps

## v3.3.0
Changes:
- Implemented [Freeze](https://docs.impulse.bot/stable/buttons/#freeze) mechanism ([silence](https://prometheus.io/docs/alerting/latest/alertmanager/#silences) analog)
- Added Prometheus [metrics](https://docs.impulse.bot/stable/api/#http-metrics-get)
- Removed log formatting
- Added [status_update](https://docs.impulse.bot/stable/config_file/#incidentnotificationsstatus_update) option
- Enabled "[some alerts resolved](https://docs.impulse.bot/stable/config_file/#incidentnotificationspartial_resolved)" notifications by default
- Removed [header](https://docs.impulse.bot/stable/concepts/incident/#__tabbed_1_3) from all Telegram thread messages

## v3.2.0
Changes:
- Added Jira support ([docs](https://docs.impulse.bot/stable/task_management/))
- Added historical data support ([docs](https://docs.impulse.bot/stable/config_file/#incidenttimeoutsclosed))
- Added support for `standby` IMPulse server ([docs](https://docs.impulse.bot/stable/ha/#two-instances))
- Fixed issue with extra logs in STDERR
- Fixed message header formatting ([issue](https://github.com/eslupmi/impulse/issues/335))
- Display "(empty)" instead of "-" in UI for users with empty names
- Removed Python 3.9 support

## v3.1.0
Changes:
- Added JSON support for webhooks ([docs](https://docs.impulse.bot/stable/config_file/#webhooksjson))
- Added Grafana as an alert source ([docs](https://docs.impulse.bot/stable/grafana/))
- IMPulse continue work on full (read-only) filesystem ([docs](https://docs.impulse.bot/stable/ha/))
- Switch to slim python docker image

Thanks:
- https://github.com/zorek187 for implementing read-only filesystem support

## v3.0.1
Changes:
- Fixed bug in scheduled chains

## v3.0.0
Upgrade instructions:
- Rename `application` with `messenger` in **impulse.yml**
- Check your configuration using `python -m main --check` before restart
- To use the **reload** functionality ([docs](https://docs.impulse.bot/stable/check/)), you need to change the startup command to `python -m main` for non-containerized installation
- Move `incident.alerts_firing_notifications` to `incident.notifications.new_firing` option in **impulse.yml**
- Move `incident.alerts_resolved_notifications` to `incident.notifications.partial_resolved` option in **impulse.yml**
- Rename `last_state` to `payload` in [ui.columns[].value](https://docs.impulse.bot/stable/config_file/#uicolumnsvalue) if you use it

Changes:
- Added config validation and `--check` option support ([docs](https://docs.impulse.bot/stable/check/))
- Added reloading configuration support using `HUP` signal
- Added Helm chart ([Artifactory Hub](https://artifacthub.io/packages/helm/impulse/impulse))
- `last_state` incident field renamed to `payload`
- `incident.notifications.new_firing` set to `True` by default
- Removed `experimental` features
- Added URL prefix support (`HTTP_PREFIX` [environment variable](https://docs.impulse.bot/stable/envs/))
- Experimental features removed
- Moved `incident.alerts_firing_notifications` to `incident.notifications.new_firing` option in **impulse.yml**
- Moved `incident.alerts_resolved_notifications` to `incident.notifications.partial_resolved` option in **impulse.yml**
- Renamed `last_state` field to `payload` in incident files
- Documentation now defaults to stable version instead of latest
- Updated documentation

Thanks:
- https://github.com/zorek187 for Helm chart realisation

## v2.8.0
Changes:
- Interface updated. Added incident details. Improved font readability
- Added assigned user's full name ([example](https://github.com/eslupmi/impulse/blob/183e75974167b403c3f46049a5e11ac35253b24b/examples/impulse.slack.advanced.yml#L92))
- Added notifications in thread about user assignment ([docs](https://docs.impulse.bot/v2.8.0/config_file/#incidentnotificationsassignment))
- Fixed template bugs

## v2.7.0
Changes:
- Added online / offline status indicator in the UI
- Added `application.type: none` support for running IMPulse without messenger integration ([docs](https://docs.impulse.bot/v2.7.0/config_file/#applicationtype))
- Removed update check functionality

## v2.6.0
Changes:
- [UI](https://docs.impulse.bot/v2.6.0/ui/) with multi-column sorting and value-based [highlighting](https://docs.impulse.bot/v2.6.0/config_file/#uicolors)
- Switched to `asyncio` for asynchronous processing
- Updated documentation and added table of contents

## v2.5.3
Changes:
- Refactor matcher logic to simplify condition checks and avoid applying regex to `None`

## v2.5.2
Changes:
- Fixed issue with parsing HTML description in Google Calendar events

## v2.5.1
Changes:
- Fixed incorrect warning about chain `None`
- Fixed a bug related to scheduled chains

## v2.5.0
Changes:
- Support for nested chains
- Documentation updated

## v2.4.0
Changes:
- Added Google Calendar support ([docs](https://docs.impulse.bot/v2.4.0/google/))
- Updated logic for **Take It** / **Release** button ([docs](https://docs.impulse.bot/v2.4.0/howto/#buttons))
- Added logging for button events
- [Telegram] Fixed incident link

## v2.3.1
Changes:
- [Telegram] Disabled **update available** functionality

## v2.3.0
Changes:
- Added [Telegram](https://telegram.org) support

## v2.2.0
Changes:
- Documentation moved to this repository

## v2.1.0
Changes:
- Added support for scheduled chains ([docs](https://docs.impulse.bot/stable/config_file/#schedule-chain))

## v2.0.0
Upgrade instructions:
- Modify `application.users`. Define users by their IDs instead of names ([docs](https://docs.impulse.bot/stable/config_file/#users))
- Add `application.channels` and define channels explicitly ([docs](https://docs.impulse.bot/stable/config_file/#channels))
- Replace Docker image `ghcr.io/ditsi/impulse` with `ghcr.io/eslupmi/impulse`
- Move `timeouts` under `incident` ([docs](https://docs.impulse.bot/stable/config_file/#all-options))
- [Mattermost] Rename `application.url` to `application.address` ([docs](https://docs.impulse.bot/stable/config_file/#all-options))
- [Mattermost] Move `url` under `application` and rename it to `impulse_address` ([docs](https://docs.impulse.bot/stable/config_file/#all-options))

Changes:
- Replaced **Chain** button with **Take It** / **Release**
- New behavior. The **Release** button restarts the chain from scratch
- Added `assigned to` field in templates with the user currently working on the incident
- Users and channels now defined by IDs only
- New **Channel** button state indicator
- Updated configuration file format

## v1.5.0
Changes:
- Added webhook timeout handling
- Fixed all known bugs

## v1.4.0
Changes:
- Major notifications format update
- Added notifications for new `firing` and some `resolved` alerts in existing incidents
- Added documentation links in notification messages
- Python 3.9 support
- Minor bug fixes

## v1.3.1
Changes:
- Fixed **update available** notification

## v1.3.0
Changes:
- Added support for private channels
- Switched [status_icons](https://github.com/eslupmi/impulse/blob/develop/templates/slack_status_icons.j2) to use `incident.status` instead of `payload.status`
- Use specific Slack workspace in incident links

## v1.2.0
Changes:
- Enabled use of incident object attributes in templates and webhooks
- Template refactoring
- Added runbook link to message templates
- Fixed user notifications for undefined users

## v1.1.0
Changes:
- Added webhook notifications to instant messengers
- Major refactoring
- Switched to WSGI for running the app
- Fixed `user` and `user_group` notifications for non-existent and undefined users
- Logging improvements

## v1.0.4
Changes:
- [Mattermost] Fixed @mention formatting

## v1.0.3
Changes:
- [Mattermost] Increased pagination limit for API requests

## v1.0.2
Changes:
- [Mattermost] Increased API limit from 60 to 1000 for `/api/v4/teams/<team_id>/channels`

## v1.0.1
Changes:
- [Slack] Increased API limit from 100 to 1000 for `api/conversations.list`

## v1.0.0
Upgrade instructions:
- Remove the `check_updates` option from **impulse.yml**
- Remove `application.message_template`, use `application.template_files` instead
- Rename `webhook.user` to `webhook.auth`

Changes:
- New incident message structure with `status_icons`, `header`, and `body`
- Added template files for incident message components
- Updated **impulse.yml** format
- [Mattermost] Fixed update payload
- Introduced new notification format
- [Mattermost] Fixed button state
- [Mattermost] Updated button payload
- Fixed `user_group` notifications

## v0.6.0
Changes:
- Added release notes to the **update available** message
- [Mattermost] Fixed update message functionality
- [Mattermost] Fixed user notification for users without a first name
- [Mattermost] Fixed bug where a declared user did not exist in the messenger

## v0.5.0
Changes:
- [Mattermost] Replaced button icons
- [Mattermost] Config now uses the displayed team name
- [Mattermost] Fixed error in **user not found** logic for `user_groups`
- [Mattermost] Fixed case-sensitivity issue with the team name in incident links
- Made the `user` field optional for Webhook
