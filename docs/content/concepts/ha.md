# High Availability

## Two instances

IMPulse allows running multiple instances to ensure high availability.

![None](../media/ha.excalidraw.svg)

The first IMPulse instance creates a `.lock.d` directory in the [DATA_PATH](../envs.md) directory to lock file operations. Other instances start in **standby** mode and wait until the first instance is shut down or becomes unavailable.

Check the `/readyz` endpoint to get the instance state. It responds with `200` if the instance is ready and **primary**, and `503` if the instance is in **standby**.

The `/livez` endpoint is used for liveness checks and always returns `200` if the container is alive, regardless of whether it's in **standby** or **primary** mode. This endpoint is available in both modes and should be used for Kubernetes liveness probes.

When running multiple IMPulse instances, configure your proxy (Nginx or another) to use the `/readyz` endpoint for readiness checks, routing traffic only to the **primary** instance. Use `/livez` for liveness checks to ensure containers are restarted if they become unresponsive. See [API](api.md) for endpoint details.

## Read-only filesystem

If the filesystem of the server where IMPulse is running becomes full, IMPulse will continue working. Data won't be lost as long as IMPulse continues running.

!!! danger "Danger"
    Do not stop or restart it

`ERROR` log messages about the issue will be produced.

This mechanism doesn't solve the problem, but protects from its consequences for some time.

To avoid such problems, configure monitoring for the server where IMPulse is running.
