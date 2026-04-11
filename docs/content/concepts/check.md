# Check and Reload

IMPulse supports configuration file validation. Use the `python -m main --check` option to validate your [configuration](../config_file.md).

IMPulse always checks `impulse.yml`[↰](../config_file.md) on startup and will not start if the configuration file contains errors.

To reload IMPulse configuration without restart, send a `HUP` signal to the process. If the new configuration contains errors, IMPulse will continue running on the old configuration, and you will see a warning in the logs.
