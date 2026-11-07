# Development Rules

| Branch | Rule | impulse | impulse-ee |
| --- | --- | --- | --- |
| feature | Merge shared changes into core first, then manually run the [sync-upstream](https://github.com/eslupmi/impulse-ee/actions/workflows/sync-upstream.yml) workflow from **develop** and review its PR before adapting Enterprise code. | | ✓ |
| feature | All **documentation** changes must be made as part of a feature, bug fix, or other related change. Documentation should not be updated independently from the change it describes. | ✓ | ✓ |

## Community and Enterprise

Keep shared behavior in `app/` and the public messenger schema in `impulse_messenger_api/`. The public step schema transports an opaque optional `if` string; Enterprise owns its grammar validation and evaluation. Put only the differing implementations and their assets in `community/` or `enterprise/`, mirroring the affected module path. Shared callers import feature facades under `app/`; those facades select an implementation using `app.edition.EDITION`. Do not modify Python's import path or choose editions per request.

`DEV_EDITION` sets `EnvironmentConfig.dev_edition` when the process starts. When unset, it selects `community`, including in an Enterprise checkout; it does not detect editions from installed source. Explicit values must be `community` or `enterprise`; empty or unknown values and a missing selected implementation are errors. Changing `impulse.yml` or reloading configuration does not switch editions.

After installing `requirements.txt` and `tests.requirements.txt`, run the shared suite in each available edition using separate processes. Tests import application configuration during collection, so `CONFIG_PATH` must point to a valid `impulse.yml` with incident timeouts and UI columns; `examples/impulse.none.yml` can be copied into an isolated configuration directory.

```bash
DEV_EDITION=community python -m pytest tests
# In the Enterprise checkout:
DEV_EDITION=enterprise python -m pytest tests
```

Build the Community image from the core checkout with `docker build --tag impulse:community .`. Enterprise image packaging is maintained in the Enterprise repository.

Implement and merge shared changes in the core repository first. After that merge, manually run the Enterprise repository's existing `sync-upstream` workflow and review its PR. Keep Enterprise implementations in its private directories; avoid copying older shared files from Enterprise over newer core code.
