# Storage

Instances that share storage elect one **primary**. Other instances start in **standby** mode and wait until the **primary** releases its lock or its lock expires. Before becoming ready, a new **primary** reloads persisted state and reconstructs its queue. All instances must use the same configuration and the same `STORAGE_BACKEND`[↰](../envs.md). See [High Availability](ha.md).

Two backends are supported: `filesystem` and `s3`.

## Filesystem

With `STORAGE_BACKEND=filesystem`, mount the same `DATA_PATH`[↰](../envs.md) on every instance.

## S3

The bucket root is the data root.

Set `STORAGE_S3_ENDPOINT_URL`[↰](../envs.md). Set `STORAGE_S3_REGION` when the storage needs an explicit region. Otherwise [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html) uses its normal region configuration.

To supply credentials for storage explicitly, set both `STORAGE_S3_ACCESS_KEY_ID` and `STORAGE_S3_SECRET_ACCESS_KEY`. When omitted, credentials use the standard [boto3 credential chain](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).

### Permissions

- `s3:ListBucket` for the bucket
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` for its objects

### Migrate to S3

1. Stop all IMPulse instances.
2. Copy the contents of `DATA_PATH`[↰](../envs.md) to the selected bucket's root, excluding `.lock.d`.
3. Enable the S3 backend.
