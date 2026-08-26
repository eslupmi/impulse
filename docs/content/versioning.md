# Versioning and Upgrade

## Versioning

IMPulse uses version numbers like **`v1.0.2`** where:

- **`1`** is a major version. It increases only when the user **must** perform manual operations to upgrade
- **`0`** is a minor version. It increases when new features or many changes are added
- **`2`** is a bugfix version. It increases when code changes are minimal

## Upgrade & Downgrade

Some minor versions update incident file contents. The `version` field in an incident indicates the IMPulse version that last updated the file; not every IMPulse version changes incidents. `--downgrade` converts the stored incident files in `<DATA_PATH>/incidents`[↰](envs.md) to an older schema and exits without starting the server.

### Upgrade process

All upgrades except major ones are automatic and require no manual intervention.

For a major version upgrade (`v1.6.0` -> `v2.0.0`) follow **Upgrade instructions** in [CHANGELOG.md](https://github.com/DiTsi/impulse/blob/develop/CHANGELOG.md). Major version upgrades must be performed sequentially: to upgrade from `v1.0.0` to `v3.0.0`, you must first upgrade to `v2.0.0`.
=== "Docker"

    1. See `impulse.yml`[↰](config_file.md) upgrade instructions in [CHANGELOG.md](https://github.com/DiTsi/impulse/blob/develop/CHANGELOG.md) (**for major version upgrade**).
    2. Set the new tag in `docker-compose.yml`.
    3. Execute `docker compose up -d`.

### Downgrade process

!!! info ""
    Downgrade is supported starting from version `v3.7.0` and allows downgrading down to `v3.6.0` (the minimum downgrade version).


=== "Docker"

    1. Stop the app (`docker compose stop`).
    2. Downgrade incident files to a specific version of IMPulse:
        ```
        docker compose run --rm app python -m main --downgrade v3.6.1
        ```
    3. Set the previous image tag in `docker-compose.yml`.
    4. Execute `docker compose up -d`.
