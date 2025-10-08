# Check and Reload

IMPulse supports configuration file validation. Use the `python -m main --check` option to validate your configuration.

IMPulse always checks `impulse.yml` on startup and will not start if the configuration file contains errors.

To reload IMPulse configuration without restart, send a `HUP` signal to the process.
