# Special Variables

IMPulse supports three special variables you can use in some [impulse.yml](../config_file.md) places:

- `env` - to access environment variables (e.g. passwords, tokens)
- `incident` - to access current incident fields (see class `Incident` [here](https://github.com/eslupmi/impulse/blob/develop/app/incident/incident.py))
- `incidents` - to access dictionary of incidents
- `payload` - to access the most recent alert payload (the `payload` variable refers to `incident.payload`)

See example [here](../integrations/external/telegram.md)
