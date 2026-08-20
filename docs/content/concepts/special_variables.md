# Special Variables

!!! warning
    The `incidents` special variable is deprecated and will be removed in `v4.0.0`

IMPulse supports special variables you can use in some [impulse.yml](../config_file.md) places and in [templates](templates.md):

- `env`[↰](../config_file.md#webhooks) - to access environment variables (e.g. passwords, tokens)
- `incident` - to access current incident fields (see class `Incident` [here](https://github.com/eslupmi/impulse/blob/develop/app/incident/incident.py))
- `payload` - to access the most recent alert payload (the `payload` variable refers to `incident.payload`)
- `previous_payload` - to access the alert payload before the latest update
- `step` - the chain step being executed. Same format as items in `incident.chain_steps` (see [API](api.md) `/api/incidents`)
- `users` - map of [messenger.users](../config_file.md#messengerusers) config names to user objects (see [API](api.md) `/api/users`)
- `user_groups` - map of [messenger.user_groups](../config_file.md#messengeruser_groups) (see [API](api.md) `/api/user_groups`)
- `groups` - map of [messenger.groups](../config_file.md#messengergroups) (see [API](api.md) `/api/groups`)
- `webhooks` - map of [webhooks](../config_file.md#webhooks) (see [API](api.md) `/api/webhooks`)
- `ui_user` - the authenticated [UI](ui.md) user who triggered the action, if any
- `parents`, `childs` - related incidents (see [inhibition](inhibition.md))

See example [here](../integrations/external/telegram.md)
