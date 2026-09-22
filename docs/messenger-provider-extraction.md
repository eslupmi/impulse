# Messenger Provider Extraction Investigation

Status: Phase 1 implemented in the working tree; Phase 0 remains deferred (decision on 2026-09-22). Phases 2–4 are not complete.

## Decision summary

Extracting messenger integrations is feasible, but the current messenger folders cannot be moved to separate packages as-is. Provider implementations inherit the shared `Application` class and import Impulse configuration, incidents, queues, templates, logging, time helpers, and authentication internals. Impulse also hard-codes the supported messenger list in configuration validation, startup, HTTP callback decoding, template loading, incident links, and UI authentication.

The recommended boundary is composition:

- Impulse keeps a `MessengerApplication` service that owns incident workflow, queues, chains, notification policy, template rendering, user caching, task management, and the rate-limited HTTP client.
- A `MessengerProvider` owns only platform-specific configuration, credentials, API requests and responses, message payloads, callbacks, links, mentions, default template resources, and optional authentication.
- The provider receives the Impulse HTTP client through a small transport protocol. It does not construct its own client or import Impulse implementation modules.
- Initially, providers live in this repository and are selected through an internal registry. External package discovery is added only after Slack, Mattermost, and Telegram all pass the same provider contract tests.

This keeps the communication machinery in Impulse while making messenger knowledge extractable.

The comprehensive Phase 0 golden-test suite is deferred, not completed or removed from the plan. The internal extraction can proceed using the existing product and mocked integration suites, focused manual verification, and targeted regression tests. Start with Slack and migrate one provider at a time. Shared provider conformance tests remain a prerequisite for external package discovery and packaging.

## User experience

The eventual Python installation flow should be:

```shell
pip install impulse impulse-slack
```

```yaml
messenger:
  type: slack
  # Slack configuration follows
```

An optional `IMPULSE_MESSENGER_PROVIDER=slack` selector can override or confirm the provider ID for deployment systems. The value is a provider ID registered by an installed distribution, not a package name or Python import path. Impulse must not install a package named by an environment variable at startup.

For reproducible containers, the connector and its pinned version should be installed while building the image:

```dockerfile
FROM impulse:<version>
RUN pip install --no-cache-dir impulse-slack==<compatible-version>
```

The current repository has no `pyproject.toml`, `setup.py`, or other Python distribution metadata, and the Docker image copies source directly into `/app`. Therefore, `pip install impulse` and external provider packaging are later delivery steps. They are not prerequisites for proving the internal split.

## Current architecture and coupling

Some useful separation already exists under `app/im/slack`, `app/im/mattermost`, and `app/im/telegram`, but the dependency direction is not suitable for external packages.

| Area | Current state | Extraction problem |
| --- | --- | --- |
| Runtime application | `app/im/application.py` combines core workflow with abstract provider hooks | Provider subclasses inherit and call private Impulse behavior |
| Startup | `app/im/helpers.py` imports every provider and uses an `if/elif` factory | Adding a provider requires editing Impulse |
| Configuration | `MessengerType` and a discriminated union enumerate four implementations in `app/config/validation.py` | An unknown third-party `type` fails before a provider can load |
| Secrets | Slack, Mattermost, and Telegram variables are fields on `EnvironmentConfig` | Adding a provider requires editing Impulse configuration code |
| HTTP callbacks | `/app` performs Slack-specific form decoding in `app/routes.py` | The core web route knows a provider wire format |
| Templates | `app/im/template.py` enumerates three messengers and reads provider-named files from the working directory | Package resources cannot be supplied by a new provider |
| Notifications | Core handlers branch on `MessengerType.TELEGRAM` to decide message composition | Core behavior depends on provider identity |
| Incident links | `Incident.generate_link` constructs Slack, Mattermost, and Telegram links | The incident domain object knows provider URL formats |
| Authentication | `app/ui/authentication/factory.py` imports every provider and branches on messenger type | A package cannot add UI authentication independently |
| Logging | URL redaction contains a Telegram-specific regular expression | New secret-bearing URL formats could leak unless providers register redaction |
| Channel typing | `ChannelManager` names every built-in channel model | External channel models are not part of the accepted type surface |

There are also provider-specific behaviors hidden in nominally core paths. Examples include Telegram-only notification composition, Telegram-specific inhibition refresh behavior, and three duplicated versions of claim/release/freeze callback handling. These should become generic commands or provider capabilities, not additional provider-name branches.

## Target ownership boundary

```text
FastAPI routes / queue / incidents / chains / maintenance
                         |
                         v
              MessengerApplication
              (Impulse-owned workflow)
                |               |
                |               +--> Impulse HTTP transport
                v
             MessengerProvider
        (platform-specific adapter only)
```

### Impulse owns

- Incident state transitions, persistence, routing, inhibition, maintenance, and queue scheduling.
- Claim, release, freeze, unfreeze, and task-creation business rules.
- Deciding when a notification is sent.
- Chain generation and user/user-group orchestration.
- Template rendering and the stable template context schema.
- User cache, configured names, admin roles, and UI serialization.
- HTTP connection lifecycle, retry policy, metrics, rate limiting, and generic secret redaction.
- Authentication sessions, whitelist enforcement, cookies, and redirects.
- Provider discovery, compatibility validation, duplicate detection, and fail-fast errors.
- The always-available `none` provider.

### A provider owns

- Its provider ID and supported plugin API version.
- Provider-specific configuration model and validation.
- Provider-specific environment variable names and required-secret checks.
- Base URLs, endpoints, request headers, response decoding, API error handling, and rate-limit declaration.
- User and group lookup and conversion to normalized Impulse profiles.
- Incident message, update, reply, action, and acknowledgement payloads.
- Callback authentication and conversion of raw callback data to generic interaction commands.
- Incident and user profile links.
- Mention formatting and other platform text rules.
- Default message and notification templates, exposed as package resources.
- An optional UI authentication provider factory.
- URL or field redaction rules needed for provider secrets.

### A provider must not receive

- Mutable `Incident`, queue, route, maintenance, or inhibition objects.
- The FastAPI application or an `aiohttp` session/response as part of the public contract.
- Impulse global configuration singletons.
- Direct access to private modules such as `app.incident`, `app.queue`, `app.routes`, or `app.config`.

Provider code runs in the Impulse process and is trusted code with the process's filesystem, environment, and network permissions. This proposal is an extension boundary, not a security sandbox. Supporting untrusted providers would require a separate process and RPC contract.

## Proposed contract

The contract should use immutable data-transfer objects containing primitives. Passing the current `Incident` object would make the first external connector depend on every future incident refactor.

The following is a shape proposal, not final code:

```python
@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    api_version: int
    rate_limit: int | None
    rate_window_seconds: float
    capabilities: frozenset[str]


@dataclass(frozen=True)
class MessageRef:
    channel_id: str
    thread_id: str


@dataclass(frozen=True)
class UserProfile:
    id: str
    exists: bool
    full_name: str | None = None
    username: str | None = None
    email: str | None = None
    timezone: str | None = None
    notification_id: str | int | None = None


@dataclass(frozen=True)
class IncidentPresentation:
    channel_id: str
    thread_id: str | None
    status: str
    header: str
    body: str
    status_icon: str
    chain_enabled: bool
    frozen: bool
    frozen_reason: str | None
    frozen_until_text: str | None
    can_unfreeze: bool
    can_create_task: bool


class InteractionAction(StrEnum):
    TOGGLE_ASSIGNMENT = "toggle_assignment"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"
    SHOW_FREEZE_OPTIONS = "show_freeze_options"
    CREATE_TASK = "create_task"
    NOOP = "noop"


@dataclass(frozen=True)
class Interaction:
    message: MessageRef
    actor_id: str
    action: InteractionAction
    freeze_option: str | None = None
    acknowledgement_id: str | None = None


class MessengerProvider(Protocol):
    descriptor: ProviderDescriptor

    async def initialize(self) -> ProviderIdentity: ...
    async def fetch_user(self, user_id: str) -> UserProfile: ...
    async def fetch_groups(self) -> Sequence[GroupProfile]: ...
    async def create_incident(self, message: IncidentPresentation) -> MessageRef | None: ...
    async def update_incident(self, message: IncidentPresentation) -> None: ...
    async def post_notification(self, message: MessageRef, content: NotificationContent) -> DeliveryResult: ...
    async def parse_interaction(self, request: InteractionRequest) -> Interaction | ProviderResponse: ...
    async def respond_to_interaction(self, interaction: Interaction, message: IncidentPresentation) -> ProviderResponse: ...
    def incident_url(self, message: MessageRef, identity: ProviderIdentity) -> str | None: ...
    def user_url(self, user: UserProfile, identity: ProviderIdentity) -> str | None: ...
```

`ProviderContext`, supplied to the provider factory, should expose only:

- A `MessengerHttpTransport` protocol implemented by `RateLimitedClient`.
- A read-only `SecretResolver` or environment mapping.
- The normalized public callback URL.
- A logger or standard Python logger name.
- The negotiated plugin API version.

The provider descriptor supplies the rate limit before the transport is created. The provider must close individual responses; Impulse owns and closes the client itself.

### Interaction handling

The `/app` route should capture method, headers, query parameters, form fields, and raw body in an `InteractionRequest` without choosing a messenger format. The provider then:

1. Verifies the callback according to the provider protocol.
2. Parses the external channel/thread/user/action values.
3. Returns a generic `Interaction`.
4. Lets `MessengerApplication` apply the business action using Impulse incidents and queues.
5. Formats or sends the provider-specific acknowledgement/update.

This removes Slack form parsing from the route and removes duplicated claim/release/freeze state transitions from provider subclasses.

### Templates and message composition

Impulse should retain `JinjaTemplate` and define the supported context for each notification event. A provider supplies a `TemplateBundle` for:

- `body`, `header`, and `status_icons`.
- Chain user, user group, group, and webhook messages.
- Assignment, status update, new firing, partial resolved, freeze, and unfreeze notifications.

Default resources must be loaded with `importlib.resources`, not relative paths such as `./templates/slack_body.j2`. Existing `template_files` overrides remain filesystem paths and keep their current precedence.

Core code passes `NotificationContent(header=..., text=...)` to the provider. The provider decides whether the platform sends only the text, prefixes a header, uses attachments, or uses another native structure. Core code no longer checks whether the provider is Telegram.

### Configuration validation

The current Pydantic discriminated union must become two-stage validation:

1. Parse YAML and read `messenger.type` as a validated provider ID string.
2. Resolve the provider descriptor from the registry.
3. Validate the messenger block with the provider's `config_model`.
4. Validate the outer `ImpulseConfig` and cross-field rules against a common `BaseMessengerConfig` interface.

The common model should retain fields Impulse genuinely uses: `type`, `channels`, `users`, `admin_users`, `user_groups`, `groups`, `chains`, `template_files`, and `impulse_address` where applicable. Provider subclasses can narrow user/channel ID types and add fields such as Mattermost `address` and `team`.

`MessengerType` must not enumerate external providers. Persisted incident values and reload comparisons can continue to use the provider ID string. `none` remains a reserved built-in ID.

Provider-specific credentials should leave `EnvironmentConfig`. A provider validates its secrets through `SecretResolver`, preserving the existing environment variable names for built-ins. This lets a third-party provider add credentials without modifying Impulse.

### Discovery

Use an internal registry during the same-repository migration:

```python
registry.register(slack_plugin)
registry.register(mattermost_plugin)
registry.register(telegram_plugin)
registry.register(none_plugin)
```

When the internal contract is proven, load external providers through the Python standard-library entry-point mechanism:

```toml
[project.entry-points."impulse.messengers"]
slack = "impulse_slack.plugin:plugin"
```

The entry-point name is the provider ID. Startup must fail before creating application state when:

- The configured provider is not installed.
- Multiple distributions register the same provider ID.
- The plugin API major version is incompatible.
- Provider configuration or required credentials are invalid.
- Required templates or declared capabilities are missing.

Discovery should be cached for one process lifetime. Installing, uninstalling, or upgrading a provider while Impulse is running is out of scope.

## Same-repository extraction plan

### Phase 0: Characterize behavior (deferred)

Decision recorded on 2026-09-22: a comprehensive golden-test suite is not a prerequisite for Phases 1–3. Use the interim verification approach below during extraction. Retain the following characterization work as a future task:

- Create/update/reply request payloads and returned thread IDs.
- User/group normalization and mentions.
- Callback parsing, verification, response payloads, and state transitions.
- Incident/user links.
- Every default template key.
- Initialization, rate limit, error, and secret-redaction behavior.

These tests define behavior, not current class inheritance. Future golden expectations should use deterministic inputs and reviewed outputs, normalizing only incidental values such as generated IDs and timestamps. Goldens created after extraction establish a baseline for the new implementation; they do not retroactively prove equivalence with the old implementation. Retain the pre-extraction commit for later comparison.

#### Existing test foundation and ownership

The following findings are based on source inspection on 2026-09-22, including Impulse commit `b3adbfb` and the local, in-progress `eslupmi/tests` working copy. They describe available infrastructure and test intent, not a passing test run:

- Impulse already has product tests for provider behavior, templates, incident/user links, HTTP retries and rate limiting, initialization logging, and URL redaction. Reuse these tests. Exact payload, response-decoding, normalization, template-rendering, and transport tests belong in this repository, including future golden tests.
- The separate `eslupmi/tests` repository has an `internal` suite that runs real Impulse containers against fake Slack, Mattermost, and Telegram HTTP APIs. It contains lifecycle, routing, notification-chain, inhibition, and Take It/Release scenarios. Complete workflows belong there; product unit/integration tests stay in Impulse.
- The internal suite currently checks endpoints, selected message content, channels, and incident state rather than full provider-body snapshots. Its button helpers do not expose Impulse's callback response body to the test. These checks provide useful workflow coverage but do not fully characterize payload structure, rendering, or callback acknowledgements.
- `DEV_MESSENGER_CUSTOM_ADDRESS` is implemented for Slack and Telegram; Slack's `auth.test` initialization request also uses the overridden address. `DEV_MESSENGER_RATE_LIMIT` and `DEV_MESSENGER_RATE_WINDOW` are applied by the shared HTTP setup, with a zero limit disabling throttling. The mocked harness uses these overrides, so its normal runs do not establish production rate-limit behavior. See [environment configuration](../app/config/environment.py), [Slack](../app/im/slack/slack_application.py), [Telegram](../app/im/telegram/telegram_application.py), and [HTTP setup](../app/im/application.py).
- CI already runs product tests, builds the PR image, and invokes a three-messenger autotest matrix. The invocation passes the candidate image explicitly through `--image`. CI checks out `eslupmi/tests` at `main`, so local or branch-only additions must be merged or explicitly selected to participate in a run. See [PR workflow](../.github/workflows/tests.yml) and [autotest workflow](../.github/workflows/_autotests.yml).

#### Interim verification for the internal extraction

1. Record the pre-extraction commit, autotest revision, and tested image. Run the existing product suite and mocked internal suites before and after the change, using the actual candidate image. Keep pre-existing failures separate from regressions and record any tests that could not run.
2. Migrate one provider at a time, starting with the Slack slice below. Use the existing suites to check the other providers and applicable `none` behavior after changes to shared code.
3. Manually verify the migrated provider's critical workflows before and after extraction: incident creation/update/resolution, threaded notifications and mentions, Take It/Release, freeze/unfreeze, and links. Check UI login if its integration changes. Record the provider, build, actions, and results; distinguish checks against mocks from checks against a real messenger.
4. Add focused regression tests for bugs exposed during extraction. Add new contract and import-boundary checks with the implementation they verify; do not require the comprehensive golden suite before starting.

This approach accepts reduced confidence in exact formatting, uncommon responses, and failure paths. Existing suites and manual checks do not establish complete behavioral equivalence. The extraction must still preserve user-facing behavior; deferral does not authorize intentional behavior changes. Revisit the deferred characterization matrix before external packaging and complete the shared conformance requirements below.

### Phase 1: Add the seam without package discovery

Add in-repository modules such as:

```text
app/im/
  application.py          # Impulse-owned orchestration facade
  plugin_api.py           # versioned protocols and DTOs
  registry.py             # internal provider registry
  interaction_service.py  # generic callback actions
  providers/
    none/
    slack/
    mattermost/
    telegram/
```

Keep the methods currently consumed by queues, routes, maintenance, and inhibition on the `Application` facade. Internally, replace abstract inheritance hooks with delegation to a `MessengerProvider`. This limits the first migration's blast radius.

Register built-ins explicitly. Do not add entry-point loading, repository splits, or config format changes in this phase.

#### Phase 1 implementation (2026-09-22)

Startup now resolves all four built-ins through `app/im/registry.py` and constructs the concrete, Impulse-owned `Application`. Its provider is a separate object, not an `Application` subclass. The old `SlackApplication`, `MattermostApplication`, and `TelegramApplication` constructors remain compatible for existing internal callers/tests, but production startup does not construct them.

```text
get_application -> internal registry -> Application
                                        |-- incident/queue/user/task workflow
                                        |-- LegacyInteractionService (temporary callback/user bridge)
                                        `-- MessengerProvider
                                             |-- immutable presentation/profile DTOs
                                             `-- injected core-owned HTTP transport
```

The implemented version-1 seam is in `app/im/plugin_api.py`: provider descriptors, identity, message references, immutable incident presentations, normalized user/group profiles, notification content/results, and HTTP transport/response protocols. The registry rejects missing/duplicate IDs, incompatible API versions, and invalid rate declarations. It does not load entry points, import configured package names, or change configuration validation.

Provider API/payload operations now live in `app/im/providers/`. Creation, updates, replies, user/group lookup, notification composition, and user-profile URLs delegate through the seam. The core renders templates and snapshots an incident before sending it to a provider; the snapshot contains primitives, including an ISO timestamp for freeze expiration. The core still creates, rate-limits, and closes the HTTP client. Providers close responses, including callback acknowledgements and failed JSON decoding. `none` remains available without a client or template files, retaining UUID incident IDs and its existing no-op behavior.

The implementation deliberately retains these **temporary Phase 1 dependencies**:

- `LegacyProviderAdapter` adapts frozen presentations to the existing payload builders. Built-ins still use the existing configuration/environment models, platform payload helpers, and default template files.
- `LegacyInteractionService` binds the existing callback and user/group orchestration methods to the single core facade. It creates no second application or user cache. Platform callback parsing, frozen-action guards, action order, and acknowledgements remain unchanged. Generic interaction-command DTOs and callback parsing move with the Phase 2/3 vertical slices.
- Routes still decode the existing callback formats; incident links, authentication selection, template resources, and remaining provider-ID checks retain their existing implementation. These are Phase 2/3 work, not completed extraction claims.
- Direct provider import checks prevent incident/queue/route/maintenance/inhibition/concrete-HTTP imports. They do **not** claim the final private-core import boundary: legacy configuration, logging, and payload-helper dependencies remain.

`tests/test_im/test_provider_seam.py` exercises the registry-created facade, transport ownership, all four built-ins, create/update/notification delivery, user normalization, assignment and frozen callbacks, Slack token rejection, Telegram freeze menus/acknowledgements, `none` freeze behavior, template override precedence, user links, immutable snapshots, registry errors, and JSON-failure response cleanup. Existing provider tests remain in place; patch targets changed where the implementation moved.

Verification uses pre-extraction commit `dea38138537651686bb40f43cb656a9c33daf1bb` and a copy of the local `eslupmi/tests` working tree based on `cc51838ca9bc2660be5bd36f354cc1ffb1d1c4ba` (including its existing uncommitted callback/operator-test work). The source test repository was not modified.

- Baseline image: `impulse:phase1-baseline-dea3813`, `sha256:9050e3f619eecf2612be8a3ddd92d4476206c6a851d455c3dfff99ba8f734a2c`.
- Candidate image: `impulse:phase1-candidate`, `sha256:7d3613588cad3f20bd2f87a7821f43a74dc5afb8a138713de1bed74c3bef883c`.
- Baseline product tests: **1,147 passed**. Final product tests: **1,172 passed** in WSL/Python 3.10 and **1,172 passed** in the candidate Linux/Python 3.12 container. Existing test-mock warnings remain.
- Ruff, `git diff --check`, and mypy over `app` and `main.py` passed (122 product source files). SHA-256 hashes of all 123 product source/dependency files in the actual candidate image match the final working-tree files.
- The final Docker messenger matrix passed identically on the baseline and candidate: **47 passed, 1 skipped** each. The skip is the existing Telegram group case. Both runs used the same temporary harness corrections described below.
- The candidate Docker `none` system suite passed **29 tests**, covering API/health, lifecycle, routing, reload, restart persistence, and WebSocket behavior.
- The first container product-test invocation reused mounted Windows bytecode whose embedded source filename was `C:\Users\tansdf-Legion\PycharmProjects\impulse\tests\conftest.py`; it failed in fixture introspection and cascaded into event-loop failures. The successful run used `PYTHONPYCACHEPREFIX=/tmp/isolated-pycache`, `--asyncio-mode=auto`, and `-o asyncio_default_fixture_loop_scope=function` with the same image and test sources. The failed log is retained.

The internal harness required task-local corrections before a meaningful before/after comparison: synchronous callback posts were moved off the fake server's async event loop, and message assertions wait up to one second for an already-queued update while retaining the same payload/channel checks. Original failures are preserved (host baseline: 3 failures; container baseline with only the callback correction: 2 observation failures). No product assertions were removed.

The first candidate container matrix additionally had four Telegram timing failures caused by a single 30-second fake-API HTTP timeout holding the queue. Its Windows fake server also logged `WinError 10022`; the exact connection-level cause is not proven. With the same product image and a selector event loop for the Windows fake subprocesses, the complete Telegram slice passed (15 passed, 1 intentional group-test skip) without a product change. The final baseline and candidate full matrices both passed with these identical harness settings. This is environment-specific verification, not a claim of a product transport fix.

Full logs, source hashes, XML results, harness corrections, and failed runs are retained in the task-local `/tmp/impulse-phase1/` evidence directory. Live Slack/Mattermost/Telegram tenant checks and interactive UI login checks were not run. Default package resources, complete callback contracts, the comprehensive Phase 0 characterization, and the Phase 2 Slack vertical slice remain separate work.

### Phase 2: Prove one complete vertical slice with Slack

Slack is the recommended first real provider because it exercises outbound messages, replies, user and group discovery, callback verification, form payloads, links, rate limits, templates, and optional UI authentication.

Move all Slack-specific logic behind `SlackProvider`, including code currently in:

- `app/im/slack/slack_application.py`.
- `app/im/slack/threads.py`, `buttons.py`, `config.py`, and `user.py`.
- Slack models currently in `app/config/validation.py`.
- Slack credentials currently in `app/config/environment.py`.
- Slack callback decoding in `app/routes.py`.
- Slack link generation in `app/incident/incident.py`.
- Slack UI authentication selection in `app/ui/authentication/factory.py`.
- Slack files under `templates/` and `thread_templates/`.

Mattermost and Telegram may temporarily use a `LegacyProviderAdapter`, but no new core type branch should be added.

### Phase 3: Migrate the remaining built-ins

Move Mattermost and Telegram through the same contract. Convert any remaining provider-name checks to generic behavior, provider presentation, or an explicitly named capability. Migrate `none` to the same contract last or first as a low-risk registry test, but do not treat it as proof that the real boundary works.

At the end of this phase:

- Core code has no imports from `providers.slack`, `providers.mattermost`, or `providers.telegram` except registration in the composition root.
- Core code has no equality checks for those provider IDs.
- Provider directories import only `plugin_api`, standard-library modules, and their own dependencies.
- Removing a built-in registration produces the same missing-provider error expected for an uninstalled package.

### Phase 4: Add package discovery and packaging

Before starting this phase, revisit the deferred characterization matrix and require Slack, Mattermost, and Telegram to pass the shared provider behavior checks. Then add Python distribution metadata, package resource handling, external entry-point discovery, API compatibility checks, and fresh-environment installation tests. Add discovery-specific checks as those features are implemented. Move one built-in provider to a separate repository only after the full applicable conformance suite and its installed-package smoke test pass.

## Initial implementation slice

The first reviewable implementation should stop after a same-repository Slack vertical slice. Its acceptance criteria are:

1. Existing `impulse.yml` Slack configuration and environment variable names are unchanged.
2. Routes, queues, incidents, maintenance, and inhibition call the Impulse-owned `Application` facade, not Slack code.
3. The facade is constructed from the internal registry and delegates Slack API/presentation work to `SlackProvider`.
4. The Slack provider receives an injected transport and does not import the concrete HTTP client.
5. Slack callbacks become generic interaction commands before incident or queue state is changed.
6. Slack default templates are resolved through the provider resource interface; user file overrides still work.
7. No core file branches on `slack`.
8. Provider import-boundary tests reject imports of private Impulse modules.
9. Existing product tests and mocked integration suites pass against the extraction candidate, with any pre-existing failures documented separately and no new regressions. Critical Slack workflows are manually verified using the interim verification approach above, including UI login if its integration changes. Comprehensive golden tests remain deferred; this evidence does not claim complete payload equivalence.
10. Mattermost, Telegram, and `none` continue to work through their existing implementation or a documented temporary adapter.

This slice proves the difficult boundary without combining it with packaging and release changes.

## Contract and packaging tests

Build focused contract tests alongside the internal implementation. Shared provider behavior checks must pass before Phase 4; `none` must satisfy its applicable no-op contract. Discovery and installed-package checks are added during Phase 4 and must pass before external delivery. These later gates do not replace the deferred Phase 0 as a prerequisite for starting Phase 1. The full suite should cover:

- Descriptor and plugin API version validity.
- Config success and failure cases.
- Missing-secret errors that name the variable but never its value.
- Initialization and cleanup with a fake transport.
- Normalized user and group results.
- Create, update, reply, link, and callback behavior.
- Required template bundle completeness.
- Callback authentication failures returning `401` or the provider-appropriate response.
- No credentials in logs, exceptions, request metrics, or rendered URLs.
- Duplicate, missing, and incompatible provider startup failures.

The external-package milestone additionally requires a clean-environment smoke test:

1. Build the Impulse distribution and one provider wheel.
2. Create an empty virtual environment.
3. Install only Impulse and that provider.
4. Run configuration validation.
5. Start Impulse with a fake provider transport or recorded API fixtures.
6. Verify provider templates load from the installed wheel.
7. Verify uninstalling the provider yields an actionable missing-provider error.

## Compatibility and versioning

- Version the provider API independently from the Impulse application version.
- Require an exact plugin API major version and allow compatible minor additions.
- Add new optional capabilities or methods with defaults; reserve major versions for breaking DTO or semantic changes.
- Keep provider IDs stable because they are persisted in incidents.
- Preserve current built-in YAML fields and environment names through the internal migration.
- Treat template context fields as part of the public plugin API.
- Do not promise cross-version compatibility until the installed-wheel test exists in CI.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| The contract leaks `Incident` or queue behavior | Use immutable snapshots and generic commands; enforce import boundaries |
| Slack, Mattermost, and Telegram callback flows differ | Model request parsing, business action, and provider response as separate steps |
| Package templates fail outside the repository working directory | Use `importlib.resources` and installed-wheel tests |
| Dynamic Pydantic models weaken cross-field validation | Use two-stage validation and retain common messenger fields on a base model |
| Third-party secrets appear in URLs or logs | Inject a secret resolver and require provider redaction declarations/conformance tests |
| Duplicate or malicious packages register an ID | Fail on duplicates; document that providers are trusted in-process code |
| Core accumulates provider capability flags | Prefer provider methods and presentation DTOs; add only semantic, provider-neutral capabilities |
| The first migration becomes a repository/packaging rewrite | Keep discovery internal until all built-ins pass the contract |
| Deferred golden tests leave formatting and edge-case regressions less visible | Retain the pre-extraction baseline, run existing suites on the candidate image, manually verify critical workflows, and add targeted regressions; do not claim complete equivalence |

## Explicit non-goals

- Running more than one messenger simultaneously. The current application selects one messenger; multi-provider routing is a separate product change.
- Installing packages dynamically at startup.
- Hot-reloading provider code or changing provider type on `SIGHUP`.
- Sandboxing untrusted provider code.
- Turning Jira, calendars, or arbitrary webhooks into messenger providers.
- Changing current Slack, Mattermost, or Telegram user-facing behavior during extraction.

## Recommendation

Proceed with the internal contract and Slack vertical slice using the interim verification approach, without waiting for the deferred Phase 0 golden suite or creating new repositories. The architectural success criterion is not that files have moved; it is that Impulse can construct and operate a provider using only the public contract, with no provider-name branches or private-core imports. Require shared conformance before external discovery and packaging. Once all built-ins satisfy that rule, standard Python entry points make external packages a packaging operation rather than another application refactor.
