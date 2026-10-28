# Storage

Instances that share storage elect one **primary**. Other instances start in **standby** mode and wait until the primary releases its lock or its lock expires. All instances must use the same configuration and the same `STORAGE_BACKEND`[↰](../envs.md). See [High Availability](ha.md).

Two backends are supported: `filesystem` and `s3`.

## Filesystem

With `STORAGE_BACKEND=filesystem`, mount the same `DATA_PATH`[↰](../envs.md) on every instance. The lock uses the existing `.lock.d` directory and heartbeat files. Keep host clocks synchronized. Heartbeat failures do not automatically demote an existing filesystem primary; see [Read-only filesystem](ha.md#read-only-filesystem).

## S3

`STORAGE_BACKEND=s3` persists incidents, users, UI schedules, maintenance windows, and authentication sessions in an existing S3 bucket. Configure the same `STORAGE_S3_BUCKET_NAME`[↰](../envs.md) on every instance. Local `DATA_PATH` directories may differ; a shared filesystem is unnecessary.

```dotenv
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET_NAME=impulse-data
```

For S3-compatible services, also set `STORAGE_S3_ENDPOINT_URL`, for example `https://s3.example.com`. Set `STORAGE_S3_REGION` when the storage needs an explicit region; otherwise Boto3 uses its normal region configuration.

To supply credentials for storage explicitly, set both `STORAGE_S3_ACCESS_KEY_ID` and `STORAGE_S3_SECRET_ACCESS_KEY`. When omitted, credentials use the [standard Boto3 credential chain](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html), including IAM roles or `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional `AWS_SESSION_TOKEN`.
The service account needs `s3:ListBucket` for the bucket and `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` for its objects. Bucket provisioning is separate. Use a separate bucket for each independent IMPulse deployment.

Data retains its existing YAML and iCalendar formats. For example, an incident is stored at `incidents/<uniq_id>.yml` in the bucket. `DATA_PATH` is not part of the S3 object keys. Configuration, templates, and Google service account files remain local.

The lock is the object `.lock.d/lease.json` at the bucket root. Atomic conditional writes elect and renew the primary, and conditional deletion prevents an old primary from removing the new primary's lock. The endpoint must provide strong consistency and support conditional `PutObject` (`If-None-Match` and `If-Match`) and conditional `DeleteObject` (`If-Match`). S3 lock expiry uses server timestamps, so it does not depend on matching client wall clocks.

To move existing filesystem data, stop all IMPulse instances and copy the contents of `DATA_PATH` to the selected bucket's root, excluding `.lock.d`. Enable the S3 backend only after the copy completes. To switch back, stop all instances and copy the current data objects back to `DATA_PATH`, excluding `.lock.d/lease.json`, before selecting `filesystem`. Run data migration and maintenance commands only while all instances are stopped.

## Lock

The lock is a record in the storage that names the current primary: the `.lock.d` directory for `filesystem` or the `.lock.d/lease.json` object for `s3`.

The primary updates the lock every 6 seconds. The filesystem heartbeat expires after 18 seconds; S3 waits one extra second before takeover because server timestamps have one-second precision. On graceful shutdown, the primary deletes the lock immediately. Before becoming ready, the new primary reloads persisted state and reconstructs its queue.

With S3, if the primary loses its lease or cannot renew it, it becomes unready, rejects new work, cancels queue processing and background tasks, and returns to standby. S3 storage errors prevent promotion. The filesystem backend retains its existing behavior and does not perform this automatic demotion.

!!! warning "In-flight operations"
    The lock only decides which instance is primary. It cannot cancel a data write or messenger request that the old primary sent before it lost the lock. If the old primary pauses for a long time or its network is slow during takeover, such operations can still complete after the new primary starts. IMPulse does not guarantee exactly-once delivery.
