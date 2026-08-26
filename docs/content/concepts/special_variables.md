# Special Variables

!!! warning
    The `incidents` special variable is deprecated and will be removed in `v4.0.0`

IMPulse supports special variables you can use in some [impulse.yml](../config_file.md) places and in [templates](templates.md):

- `childs` - map of `uniq_id`s to `incident` objects this incident inhibits (see [inhibition](inhibition.md))
- `env` - to access environment variables (see [example](../integrations/external/telegram.md))
- `groups` - map of [messenger.groups](../config_file.md#messengergroups) (see [API](api.md) `/api/groups`)
- `incident` - to access current incident fields (see [API](api.md) `/api/incidents`)
- `incidents` - incidents store (`incidents.uniq_ids` is the `uniq_id` → incident map). Deprecated, use `parents` / `childs` instead
- `parents` - map of `uniq_id`s to incident objects that inhibit this incident (see [inhibition](inhibition.md))
- `payload` - to access the most recent alert payload (the `payload` variable refers to `incident.payload`)
- `previous_payload` - to access the alert payload before the latest update
- `step` - the chain step being executed. Same format as step in `incident.chain_steps` (see [API](api.md) `/api/incidents`)
- `ui_user` - the authenticated [UI](ui.md) user who triggered the action, if any
- `user_groups` - map of user groups (see [API](api.md) `/api/user_groups`; users: `/api/users`)
- `users` - map of users (see [API](api.md) `/api/users`)
- `webhooks` - map of webhooks (see [API](api.md) `/api/webhooks`)
