# Upgrade

For the major version upgrade (**`v1.6.0` -> `v2.0.0`**) you should follow `Upgrade instructions` in [CHANGELOG.md](https://github.com/DiTsi/impulse/blob/develop/CHANGELOG.md). Major version upgrades must be performed sequentially: to upgrade from **`v1.0.0`** to **`v3.0.0`**, you must first upgrade to **`v2.0.0`**.

Another upgrades can be done without manual operations.

To understand our versioning model see [Versioning](versioning.md).

<!-- ### Python -->

## Docker

1. See `impulse.yml` upgrade instructions in [CHANGELOG.md](https://github.com/DiTsi/impulse/blob/develop/CHANGELOG.md) (**for major version upgrade**).
2. Set new tag in `docker-compose.yml`.
3. Execute `docker-compose up -d`.

<!-- ## Downgrade

Minor version downgrade can break functionality because some of them can contain incident objects updates. 

### Docker -->


