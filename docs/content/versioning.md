# Versioning and Upgrade

## Versioning

IMPulse uses version numbers like **`v1.0.2`** where:

- **`1`** is a major version. It increases only when the user **must** perform manual operations to upgrade
- **`0`** is a minor version. It increases when new features or many changes are added
- **`2`** is a bugfix version. It increases when code changes are minimal

## Upgrade & Downgrade

!!! info ""
    Downgrade is supported starting from version `v3.6.0`

For the major version upgrade (`v1.6.0` -> `v2.0.0`) you should follow **Upgrade instructions** in [CHANGELOG.md](https://github.com/DiTsi/impulse/blob/develop/CHANGELOG.md). Major version upgrades must be performed sequentially: to upgrade from `v1.0.0` to `v3.0.0`, you must first upgrade to `v2.0.0`.

Other upgrades can be done without manual operations.

### Upgrade process

=== "Docker"

    1. See `impulse.yml`[↰](config_file.md) upgrade instructions in [CHANGELOG.md](https://github.com/DiTsi/impulse/blob/develop/CHANGELOG.md) (**for major version upgrade**).
    2. Set the new tag in `docker-compose.yml`.
    3. Execute `docker compose up -d`.
