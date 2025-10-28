# HA

## Read-only filesystem

If the filesystem of the server where IMPulse is running becomes full, IMPulse will continue working. Data won't be lost as long as IMPulse continues working.

!!! danger "Danger"
    Do not stop or restart it

`ERROR` log messages about the issue will be produced.

This mechanism doesn't solve the problem, but protects from its consequences for some time.

To avoid such problems, configure monitoring of the server where IMPulse is running.
