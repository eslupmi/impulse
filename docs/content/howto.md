# How to use

When alert occurs, new incident will be created. If incident has **chain**, chain will start execution.

## Buttons

If user press **Take It** button, incident will be assigned to him and chain will be stopped.

If user fixed the problem and need to recreate incident chain from scratch, he should press **Release** button. It may be helpful if chain contains calls (see [Configuration](config_file.md#webhooks)) which already done and you need to recreate chain to get calls again for new **firing** status.

Sometimes incident has many switches between **firing** and **resolved** statuses. To disable **status update** messages you can use **Status** button. By default it enabled (green indicator). Red indicator means 'disabled'.
