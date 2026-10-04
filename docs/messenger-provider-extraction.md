# Messenger Provider Extraction Investigation

Status: Phases 1–3 are complete. Phase 4 is implemented locally on 2026-10-03: Slack, Mattermost, and Telegram are independent distributions in the sibling `impulse-messengers` repository, and IMPulse discovers installed providers. The local verification record and remaining qualification limits are below. Phase 0 remains deferred; no packages have been published.

## Decision summary

At the investigation baseline, messenger integrations could not be moved to separate packages as-is. Provider implementations inherited the shared `Application` class and imported Impulse configuration, incidents, queues, templates, logging, time helpers, and authentication internals. Impulse also hard-coded the supported messenger list in configuration validation, startup, HTTP callback decoding, template loading, incident links, and UI authentication.

The recommended boundary is composition:

- Impulse keeps a `MessengerApplication` service that owns incident workflow, queues, chains, notification policy, template rendering, user caching, task management, and the rate-limited HTTP client.
- A `MessengerProvider` owns only platform-specific configuration, credentials, API requests and responses, message payloads, callbacks, links, mentions, default template resources, and optional authentication.
- The provider receives the Impulse HTTP client through a small transport protocol. It does not construct its own client or import Impulse implementation modules.
- Phases 1–3 prepared the contract with an internal registry. Phase 4 moves the three messaging providers into independent packages and discovers their registrations through `impulse.messengers`; `none` remains built into IMPulse.

This keeps the communication machinery in Impulse while making messenger knowledge extractable.

The comprehensive Phase 0 golden-test suite is deferred, not completed or removed from the plan. The internal extraction can proceed using the existing product and mocked integration suites, focused manual verification, and targeted regression tests. Start with Slack and migrate one provider at a time. Shared provider conformance tests remain a prerequisite for external package discovery and packaging.

## User experience

After compatible package publication, the Python installation flow will be:

```shell
uv venv
uv pip install impulse-bot impulse-slack
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
RUN uv pip install --python /app/.venv/bin/python impulse-slack==<compatible-version>
```

At the investigation baseline the repository had no Python distribution metadata. Phase 4 now packages the application as `impulse-bot` and manages dependencies with uv. Until publication, use the local wheel installation commands in [the README](../README.md#python-packages-and-development).

## Baseline architecture and coupling (before Phase 1)

The baseline already had some separation under `app/im/slack`, `app/im/mattermost`, and `app/im/telegram`, but its dependency direction was not suitable for external packages.

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

The current built-in lifecycle uses `initialize(context)` to attach the transport and callback URL and resolve identity. Core then loads users, user groups, groups, and admin roles before calling `activate()`. Telegram registers its webhook during activation; Slack and Mattermost have no activation work. The initialization success log follows activation.

Provider JSON helpers return only the decoded body and close the response even when decoding fails. Callers retain HTTP status checks, including skipping JSON decoding for failed user/group lookups.

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

Configured users share a core schema with a required, non-empty string or integer `id`; booleans are rejected. Slack and Mattermost narrow IDs to strings, and Telegram narrows them to integers while retaining numeric-string input compatibility. Built-in messaging user schemas expose only `id`. Legacy Telegram `name`/`username` configuration fields are ignored; runtime names and handles still come from provider lookup and the user cache. Authentication retains the YAML user key as its username fallback and enriches missing fields from the cache. The UI-only `none` configuration keeps unused user entries permissive.

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
- `DEV_MESSENGER_CUSTOM_ADDRESS` is implemented for Slack and Telegram; Slack's `auth.test` initialization request also uses the overridden address. `DEV_MESSENGER_RATE_LIMIT` and `DEV_MESSENGER_RATE_WINDOW` are applied by the shared HTTP setup, with a zero limit disabling throttling. The mocked harness uses these overrides, so its normal runs do not establish production rate-limit behavior. See [environment configuration](../app/config/environment.py), `impulse_slack`, `impulse_telegram`, and [HTTP setup](../app/im/application.py).
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

The planned slice moves Slack-specific logic behind `SlackProvider`, covering these Phase 1 source locations:

- `app/im/slack/slack_application.py`.
- `app/im/slack/threads.py`, `buttons.py`, `config.py`, and `user.py`.
- Slack models currently in `app/config/validation.py`.
- Slack credentials currently in `app/config/environment.py`.
- Slack callback decoding in `app/routes.py`.
- Slack link generation in `app/incident/incident.py`.
- Slack UI authentication selection in `app/ui/authentication/factory.py`.
- Slack files under `templates/` and `thread_templates/`.

Mattermost and Telegram may temporarily use a `LegacyProviderAdapter`, but no new core type branch should be added.

#### Phase 2 implementation record (2026-09-23)

Work started from a clean `6c2ae34d35f9247efc72b8f3daadc390a6fa91c7` checkout. Slack is now implemented by the independent `SlackProvider` in the sibling `impulse_slack` package, with no `Application` inheritance, `LegacyProviderAdapter`, `LegacyInteractionService`, or private-core imports. The old Slack application, payload/user helpers, and UI authentication implementation were removed. Mattermost, Telegram, and `none` retain their Phase 1 paths; they were not migrated to the new Slack interaction/authentication contracts.

```text
HTTP /app raw request
    -> Application -> SlackProvider verification and decoding
    -> immutable Interaction commands -> core interaction service
    -> incident/queue/task changes -> immutable presentation
    -> SlackProvider acknowledgement -> HTTP response

UI login -> core session manager -> registered authentication adapter
    -> Slack OpenID protocol + injected core HTTP transport
    -> normalized identity -> core whitelist/session/cookie/redirect policy
```

The public API now includes raw request and serialized response DTOs, ordered interaction commands, a secret resolver, a normalized authentication identity/protocol, and presentation fields for the formatted freeze expiration and task-button eligibility. The provider never receives incidents, queues, user stores, global configuration, an HTTP session, or a FastAPI object. Public shared configuration definitions live in `plugin_config.py` and are exposed to Slack through `plugin_api.py`; Pydantic was already a dependency.

Configuration validation resolves `messenger.type` through the internal registry before validating the selected model. Slack owns its channel/user/group/config models. Shared chain/reference checks and persisted built-in IDs remain compatible. The original validation field order is preserved. `SerializeAsAny` retains provider-specific fields such as Mattermost `address` and `team` through outer configuration serialization; regression tests exercise all four model round trips. Legacy runtime factories are lazy so configuration validation cannot import incident/runtime state recursively. Their descriptor metadata is checked against the instantiated providers.

Slack reads `SLACK_BOT_USER_OAUTH_TOKEN` and `SLACK_VERIFICATION_TOKEN` from the injected read-only environment snapshot; these names and existing YAML fields are unchanged. Missing required credentials produce errors containing variable names, never values. An optional `SLACK_SIGNING_SECRET` enables HMAC verification over the exact raw bytes with a five-minute timestamp bound; when configured, unsigned verification-token fallback is disabled. Existing verification-token installations continue to work. The implementation follows Slack's [request verification protocol](https://docs.slack.dev/authentication/verifying-requests-from-slack/). Malformed requests and failed verification are rejected before incident lookup. A callback carrying a different channel cannot act on a matching timestamp in another channel.

Slack owns API endpoints, headers, response normalization, message/update/reply payloads, status colors, buttons, links, Markdown conversion, and all 13 default Jinja resources. Resources use `importlib.resources`; body/header/status-icon file overrides retain precedence. Existing mention syntax and rendered template sources are unchanged. Core owns user caching, admin roles, group orchestration, presentation rendering, freeze-time calculation, and task eligibility. Take It/Release, freeze/unfreeze, frozen-action guards, batch order, task dispatch, and callback acknowledgements retain their business behavior.

UI authentication is selected by the registry's optional authentication factory. Slack's [OpenID flow](https://docs.slack.dev/authentication/sign-in-with-slack/) owns authorization URLs, token exchange, and user-info normalization. The core adapter injects and closes its HTTP transport, without automatic retries of one-use authorization codes. Whitelist enforcement, state consumption, sessions, cookies, redirect restrictions, and logout stay in the existing core manager. No frontend UI was redesigned.

| Initial slice criterion | Phase 2 implementation and evidence |
| --- | --- |
| 1. Configuration/environment compatibility | Provider-owned Slack models; original YAML/secret names; blank development override fallback; config and round-trip regressions. |
| 2. Core facade ownership | `/app` forwards raw DTOs to `Application`; incident links call the facade; state transitions live in `app/im/interactions.py`; queues/maintenance/inhibition continue using the facade. |
| 3. Registry construction | `get_application` selects `SlackProvider` from the internal registry; Slack's legacy service is absent. |
| 4. Injected transport | Slack receives only `MessengerHttpTransport`; initialization/delivery/auth tests cover response and client cleanup. |
| 5. Generic callback commands | Verification and full decoding precede core lookup/mutation; callback tests cover malformed inputs, frozen guards, assignment/release, all freeze options, unfreeze, task actions, and response bodies. |
| 6. Provider resources/overrides | All 13 resources load in a fresh process outside the repository cwd; all three file override keys are tested. No external package installation is claimed. |
| 7. No core Slack branches | Core selection uses registration/protocol support; AST tests reject Slack equality branches and provider imports outside registration. The retained built-in enum is static schema, not discovery. |
| 8. Import boundary | Recursive AST checks resolve relative imports; a fresh-process import guard blocks private configuration, incident, queue, logging, UI, HTTP, user, application, and legacy modules. |
| 9. Product/workflow verification | Product suites, Docker matrices, and baseline/final HTTP operator walkthroughs are recorded below. Live-tenant and browser-rendering gaps remain explicit. |
| 10. Other messengers | Original Mattermost/Telegram/none adapters remain; the three-messenger matrix and `none` contract/system suite provide regression evidence. |

Verification uses the same task-local corrected harness as Phase 1, copied from the retained local `eslupmi/tests` snapshot based on `cc51838ca9bc2660be5bd36f354cc1ffb1d1c4ba`. It retains callback posts off the fake server's async event loop, the bounded observer wait with unchanged message/channel assertions, and the Windows selector loop. The source test repository was not edited. Messenger rate overrides remain enabled in these mocks; they do not establish live Slack throttling behavior.

- Baseline image: `impulse:phase2-baseline`, `sha256:787bc32e73d3b4a232937d040f9384c299db17af7924923de62f09773d68904b`.
- Final image: `impulse:phase2-final`, `sha256:be1dcb44c7a7f997cafdf6f6d72c7931eb6896bdedce4c62957469ee4e7fba63`.
- All **195** selected product, dependency, static, and template files in the final image match their working-tree SHA-256 hashes.
- Baseline product suite: **1,172 passed**. Final WSL/Python 3.10 product suite: **1,235 passed** (28 existing mock/deprecation warnings). Final Linux/Python 3.12 candidate-container product suite: **1,235 passed** (31 existing mock/deprecation warnings).
- The baseline and final Docker messenger matrices each passed **47 tests**, with **1 existing Telegram group skip**.
- The final Docker `none` contract/system suite passed **29 tests**, covering API/health, lifecycle, routing, reload, restart persistence, and WebSocket behavior.
- Baseline and final Slack operator walkthroughs each passed **15 checks**, including Jira task creation and the UI authentication HTTP flow.
- Ruff and mypy passed (122 product source files); `git diff --check` passed. The 13 moved Slack template files also match their baseline contents byte for byte.

The operator walkthrough runs the actual Docker application with local fake Slack and Jira servers. It directly posts form callbacks and inspects acknowledgement bodies and persisted state. It covers creation, updates, resolution, Take It/Release, invalid-token rejection, freeze/unfreeze, the frozen task guard, task creation, links, threaded notifications/mentions, and the UI authentication HTTP flow: authorize redirect, token exchange, session cookie, `/auth/me`, replay rejection, logout, and whitelist rejection. Only the authentication endpoint URLs are redirected by a task-local bootstrap; session policy and product authentication code run unchanged. This is real HTTP/Docker execution against fake services, not a live Slack workspace or a browser-rendering check.

Boundary regressions also cover immutable commands, signed-body tampering/staleness/malformed headers, response cleanup, non-JSON user/group HTTP errors, no reflected secrets in API failure logs, normalized users/groups/admins, malformed configuration IDs, and the strict raw-request facade contract. The original provider tests were retargeted to the new public boundary rather than retaining a second Slack application solely for tests.

Failed preparation and intermediate runs are retained alongside the passing evidence. Docker initially treated a tar stdin context as Dockerfile text; building the isolated source directory corrected this. A prematurely started intermediate matrix reported 13 missing-image setup errors; it is not candidate workflow evidence. A Linux Docker CLI rejected Windows drive-letter mount syntax; container product tests use the native Windows CLI. Auth test assumptions were corrected to the existing local error redirects and secure-cookie policy. These harness/setup corrections are separate from product fixes. Configuration validation order and subclass serialization regressions exposed during implementation were fixed and retested.

Full logs, XML, source hashes, callback response records, task-local scripts, and failures are retained under `/tmp/impulse-phase2/`. Container product tests use `PYTHONPYCACHEPREFIX=/tmp/isolated-pycache`, `--asyncio-mode=auto`, and function-scoped asyncio fixtures, retaining the Phase 1 bytecode correction.

**Scope and gaps:** no live Slack/Mattermost/Telegram tenant requests were made. The browser tool could not start in this WSL workspace (`sandboxCwd is not a local file URI`); login was verified through the actual HTTP authentication flow, not visually in a browser or at Slack's hosted consent screen. The comprehensive Phase 0 golden suite and installed-wheel conformance remain deferred. No package discovery or external packaging was performed. This Phase 2 slice was later committed as `d97fb67`.

### Phase 3: Migrate the remaining built-ins

Move Mattermost and Telegram through the same contract. Convert any remaining provider-name checks to generic behavior, provider presentation, or an explicitly named capability. Migrate `none` to the same contract last or first as a low-risk registry test, but do not treat it as proof that the real boundary works.

#### Phase 3 implementation record (2026-09-23) — complete

Phase 3.1 migrated Telegram after the staged Mattermost and `none` work. `TelegramProvider` in the sibling `impulse_telegram` package owns its YAML model, `TELEGRAM_BOT_TOKEN` from the injected read-only secret snapshot, API requests, payloads, callback decoding into immutable commands, links, numeric mentions, and all 13 default Jinja resources. The existing file overrides retain precedence. `DEV_MESSENGER_CUSTOM_ADDRESS` still replaces the Telegram API base, and the descriptor retains the 60-second user-refresh gap. The provider contract now expresses header-less notifications, the inhibition source refresh skip, and HTML autoescape. The registered Telegram OpenID adapter uses the injected core HTTP transport and retains signed ID-token/JWKS verification; core session and whitelist policy remains shared.

The old `app/im/telegram` package, legacy Telegram adapter module, Telegram UI auth provider, and Telegram template files under `templates/` and `thread_templates/` are removed. Core imports from the three provider packages occur only in the registry, and core has no equality checks for their IDs. Telegram templates were moved byte for byte.

The temporary bridge is removed with the rest of Phase 3. `LegacyProviderAdapter`, `LegacyInteractionService`, and the facade branches that called them are gone. Startup always constructs `Provider(config, secrets)` and one `Application`.

Mattermost is now `MattermostProvider` in the sibling `impulse_mattermost` package. It does not inherit `Application` or use the legacy adapter. It owns its config model, `MATTERMOST_ACCESS_TOKEN`, API calls, button payloads, callback decoding, incident and profile links, username mentions, and all 13 default Jinja resources via `importlib.resources`. Callbacks become immutable interaction commands before incident changes. OpenID login uses the same registered authentication adapter as Slack, with the Mattermost server address taken from configuration. `none` is [NoneProvider](../app/im/providers/none.py) with its own config model, no legacy `NullApplication`, and no HTTP client. User-refresh spacing lives on the provider descriptor (Mattermost 2 seconds, Telegram 60 seconds, otherwise 1 second) instead of a core messenger-name map.

The old `app/im/mattermost` package, `app/im/null`, Mattermost UI auth provider, and Mattermost files under `templates/` and `thread_templates/` are removed.

The Mattermost/`none` slice verification on Windows, Python 3.12: **1,231 passed**. One pre-existing assertion failed because `config_file_path` joins with the platform separator. Seven tests errored because this interpreter has no `aiohttp_server` fixture. The Docker messenger matrix, live tenants, and browser login were not run for that slice.

For the final Phase 3.1 working tree, focused Telegram/provider tests passed with Windows `py -3.12`; the affected provider, config, incident, queue, inhibition, template, and auth suites passed **612 tests** with the same platform-path assertion and missing `aiohttp_server` fixture excluded. The signed Telegram OpenID test uses a generated RSA key and fake injected transport; it does not prove a live Telegram consent flow. At that implementation checkpoint, no Docker messenger matrix, live tenant, or browser run had been performed for Phase 3.1. The later Docker verification is recorded below.

Phase 3 closes with these conditions met:

- Core code has no imports from `providers.slack`, `providers.mattermost`, or `providers.telegram` except registration in the composition root.
- Core code has no equality checks for those provider IDs.
- Provider directories import only `plugin_api`, standard-library modules, and their own dependencies.
- Removing a built-in registration produces the same missing-provider error expected for an uninstalled package.

#### Phase 3 verification and shared contract review (2026-09-25)

The final candidate was built from commit `d97fb673513d76e3247f717fcfe29c3996cb4983` plus the then-uncommitted Phase 3 product changes. Image `impulse:phase3-final` has ID `sha256:e90d78ff697bedc7b30d500ae2aa8dd4f29bdd022878657d25396f00c1ec7cd1`. SHA-256 manifests for all **154** selected Python, Jinja resource, entry-point, and requirement files match between the working tree and that image. No package release was made.

- The final product suite passed **1,232 tests** on WSL/Python 3.10 (24 warnings) and **1,232 tests** in the candidate Linux/Python 3.12 container (26 warnings). The container run mounted the repository read-only, supplied `examples/impulse.none.yml` at `/config/impulse.yml`, and isolated Python bytecode under `/tmp`.
- The final image passed the mocked Docker messenger matrix: Slack **16 passed**, Mattermost **16 passed**, and Telegram **15 passed, 1 existing group skip**. These suites exercise lifecycle, routing, notification chains, inhibition, and Take It/Release against fake provider APIs.
- The same image passed the deterministic `pr` suite: **35 passed** across `none` API/system workflows and fake-Mattermost OAuth, actions, retries, and chains. This is HTTP/Docker evidence, not a live tenant or rendered-browser check.
- Ruff passed for `app`, `main.py`, and the four test files edited in this verification pass; staged and unstaged `git diff --check` passed. A broader `ruff check tests` reported 41 violations outside those focused files. Mypy was unavailable in this WSL interpreter and was not run.

The shared seam tests now check all four built-in descriptors and config-model bindings, secret-name failures, normalized user/group profiles and response cleanup, incident links, malformed callback responses, all 13 required template resources for each messaging provider, and the `none` no-op contract. Existing shared and provider tests also cover facade construction, create/update/reply delivery, valid interaction commands, registry failures, template overrides, and Slack signed callback rejection. This revisits the deferred Phase 0 matrix at the behavior level; it is not a complete set of historical wire-payload goldens or proof of byte-for-byte equivalence.

That audit exposed two Telegram log leaks: provider API error descriptions could echo a bot token, and transport failures on `DEV_MESSENGER_CUSTOM_ADDRESS` logged the token-bearing URL and exception detail. Focused tests reproduced both failures. Telegram now logs status without provider response text; the core passes the provider's redactor into its HTTP client and uses it for initialization failure fields. The exact failing tests and the full product suite passed after the fix. Request metrics use status/error labels without URLs.

Verification used a task-local copy of the local `eslupmi/tests` checkout at `1fcd5b0b1166982d1bca71c363007e41abae2429`, including its pre-existing uncommitted work (source diff SHA-256 `0feb64dfef22ac81f143c89c766cc690d00c0099ffdc95ed9aec7531dfaf0884`). The source test checkout was not edited. Its original Telegram Take It/Release run timed out because a fake server made a blocking callback POST on its own async event loop while Impulse called back into that server; the failed log is retained. In the task-local copy, the three fake callback posts use a worker thread. The exact Telegram case then passed, followed by the full matrix. The first deterministic fake-Mattermost run had four WSL `ConnectTimeout` failures when the host test client followed a `host.docker.internal` OAuth redirect; a task-local rewrite to `127.0.0.1` for that fake authorization hop made the exact login test and final 35-test suite pass.

The first Python 3.12 container attempt lacked `/config/impulse.yml`. After mounting it, 177 async tests failed because a new synchronous Telegram OpenID test used `asyncio.run()`, clearing the event loop expected by the pinned `pytest-asyncio` version. Converting that test to an async pytest case removed the cascade; the final container suite passed with the repository's pinned test requirements. Failed runs and final logs/XML/manifests are retained under `/tmp/impulse-phase3-*`.

**Remaining evidence and contract limits:** no live Slack, Mattermost, or Telegram tenant was contacted, and no provider login was inspected in a rendered browser; Playwright is unavailable in this WSL runtime. The mocks override messenger rate limits, so the matrix does not prove production throttling. Mattermost and Telegram currently parse well-formed callbacks without an independent authenticity check; the tests establish malformed-request rejection and existing workflow behavior, not callback origin. The comprehensive Phase 0 goldens, discovery-specific checks, installed-wheel smoke test, and external packaging remain open. Resolve the callback-authentication contract before claiming the full external-provider conformance gate.

### Phase 4: Add package discovery and packaging

The local extraction uses one sibling repository with three independently buildable libraries: `impulse-slack`, `impulse-mattermost`, and `impulse-telegram`. Each library requires the matching `impulse-bot` distribution, exposes a `ProviderRegistration` entry point, and includes all 13 default templates. The original three provider directories are removed from IMPulse. The always-available `none` provider stays in core.

`impulse_messenger_api` is the sole public contract shipped by IMPulse. It contains DTOs, transport/authentication protocols, shared configuration schema, required template names, and registration metadata. Core and provider consumers import it directly; the former internal API/schema re-exports and closed messenger enum are removed. Provider modules import the public package and their own dependencies only. Configuration IDs are plain strings, including built-ins, so incident and user-cache YAML keeps its scalar `messenger_type` values and accepts registered third-party IDs.

The process-local registry indexes `impulse.messengers` metadata once and retains the built-in `none`. It imports and validates only the entry point named by the configured `messenger.type`, then caches its registration after validation succeeds. Duplicate selected IDs, entry-point name mismatches, incompatible API versions, invalid rate declarations/factories/config models, and missing templates fail before application initialization. Unused providers are never imported or validated, so their load/registration errors or duplicate IDs do not block startup. Installed entries named `none` remain unloaded and cannot replace the built-in provider. Load/resource errors name the selected provider without copying a potentially secret-bearing exception. A missing provider produces an install-and-restart error; startup never installs packages.

Both repositories manage application and test dependencies through uv project metadata and lockfiles. IMPulse's default development group installs core test/lint tools; core declares no messenger dependency or sibling source override. The messenger repository is a virtual workspace whose three members have separate wheel/sdist metadata and runtime dependencies. Its default development group supplies the shared test/lint tools, and `uv sync --all-packages --locked` installs all providers with the sibling core in editable mode. This workspace owns the coordinated test environment; distribution metadata contains version requirements, without local paths. The root pip requirement exports are removed; `pyproject.toml` and `uv.lock` are the dependency sources.

The installed core bundles `main.py`, UI assets, and Jira templates. Resource defaults resolve from the package when installed; configured template overrides retain their filesystem behavior. The Dockerfile uses the frozen core lock and accepts provider wheels through `wheelhouse/`. A source-only core image supports `none`; the full-image workflow checks out the sibling repository and builds all three provider wheels first. Core synchronization, builds and lint CI work without a messenger checkout. Core integration-test CI still checks out both repositories and prepares a writable temporary copy before synchronizing the messenger workspace. Messenger CI also runs the full core suite. Coordinated remote workflows require the matching changes in both repositories.

The full test sources stay in core and include real-provider integration cases; they require all three installed libraries. From the synchronized `impulse-messengers` workspace, keep the test working directory in core while selecting the combined environment:

```shell
uv run --project "$PWD" --directory ../impulse --all-packages --no-sync python -m pytest tests/ -q
```

Run the durable installed-distribution gate from `impulse-messengers`:

```shell
python3 scripts/verify-packages.py --keep-artifacts
```

The gate builds all four sdists/wheels, rebuilds wheels from the sdists with uv sources disabled, checks metadata and resources, installs core alone and core plus each individual provider in fresh environments, and runs isolated processes outside the checkout. It exercises configuration, the CLI, templates/UI/Jira resources, missing credentials, fake-transport initialization/user lookup/create/update/notification/callback rejection, response/transport cleanup, and discovery after uninstall. It also checks plain-string IDs through user-cache YAML. The core integration tests keep workflow and authentication coverage; packaging does not change callback security policy.

#### Local Phase 4 evidence (2026-10-03)

- Final WSL/Linux Python 3.10 product suite: **1,318 passed**, with 26 warnings; log `/tmp/impulse-extraction-product-final.log` and JUnit report `/tmp/impulse-extraction-product-final.xml`. This includes real installed metadata discovery, arbitrary third-party IDs, shared provider behavior, resources, authentication, and eight built-in YAML/cache/migration regression cases.
- The installed-package script rebuilt all four wheels from their source distributions with sources disabled. The clean core-only and three individual-provider environments passed configuration/CLI/resource checks, all applicable fake-transport facade lifecycle checks, and missing-provider detection after uninstall. Final artifacts and per-command logs are retained in the task-local verification directory reported by the script; no editable imports are used in those probes. Public API and provider typing markers are included.
- Both uv lockfiles pass `uv lock --check`; core and messenger workspace synchronization passed. A standalone frozen core install with no sibling provider sources passed, and the writable-copy CI preparation was exercised locally.
- The configured correctness lint gate and both repository whitespace checks pass. Ruff selection is explicit to preserve the prior gate when its default rules change. Full mypy still reports the unchanged nullable user lookup in `app/im/application.py:564`; running its repository-root command also includes two errors in pre-existing Windows `venv/Scripts/activate_this.py`. Scoped resource/Jira type checks pass. These unrelated issues are retained.

#### Compatibility cleanup (2026-10-03)

Core and test consumers now import the public SDK/schema directly. The internal
API/schema forwarding modules, closed messenger enum, configuration re-exports
and aliases, unused address-validation base, empty chain model, dictionary user
lookup bridge, artificial platform-user test aliases, and orphaned core color
table are removed. User lookup takes a string or integer ID directly. Root pip
requirement exports are removed; uv metadata and lockfiles manage dependencies.
Scoped bytecode for retired modules was removed as well.

The final WSL/Linux Python 3.10 suite passed **1,342 tests**, with 26 warnings;
three tests for the removed messenger enum were retired. Runtime and library
Ruff checks passed. Rebuilt source distributions passed all four isolated
core/provider installation, discovery, delivery, resource, and uninstall checks.
Source-import and wheel checks explicitly reject retired messenger modules.
Logs: `/tmp/impulse-cleanup-product-final.log` and
`/tmp/impulse-cleanup-wheel-final.log`. This adds no live-tenant, Docker, or hosted
CI evidence.

#### Distribution version alignment (2026-10-03)

Core and all three messenger distribution versions match. Provider wheel
metadata pins the matching core distribution, and both uv lockfiles retain their prior
third-party dependency versions. Both locked editable environments synchronize
successfully and report the same four installed release versions.

The installed-package gate rebuilt all four source archives into wheels and
passed the core-only and three individual-provider environments.
It now rejects unequal wheel or installed distribution versions and requires an
exact matching core dependency. The harness's two stdlib tests and library Ruff
checks passed. Log: `/tmp/impulse-380-package-final.log`; artifacts and command
logs: `/tmp/impulse-package-verification-rnouq32z`. No live-tenant, Docker, hosted
CI, or publication evidence is added by this metadata change.

#### Configured-provider loading (2026-10-04)

Entry-point metadata is indexed once without imports. Configuration resolves only
its `messenger.type`, and the selected registration is cached after all validation
succeeds. Failed selected loads remain retryable. Invalid or duplicated unused
providers stay unloaded; installed `none` entries cannot replace the built-in.
Selected missing/duplicate/incompatible providers and secret-safe load/resource
errors still fail clearly before application initialization.

The final WSL/Linux Python 3.10 suite passed **1,345 tests**, with 25 warnings;
focused discovery/provider contract checks passed **92 tests**. Runtime and
messenger harness Ruff checks passed, as did the two stdlib harness tests. The
installed-package gate rebuilt all four sdists into wheels and passed its
existing isolated core/provider lifecycle and uninstall matrix. With all three
libraries installed together, four fresh processes verified that configuration,
facade construction and imports of core `main`/routes/authentication load only
the selected external provider; `none` loads none. The import checks do not start
the server or its lifespan. Logs: `/tmp/impulse-lazy-product-final.log` and
`/tmp/impulse-lazy-packages-final.log`; package evidence:
`/tmp/impulse-package-verification-zwu2gi57`. This adds no live-tenant, Docker,
hosted CI or publication evidence. Distribution and SDK versions are unchanged.

#### Development dependency separation (2026-10-04)

Core's messenger dependency group, sibling source overrides and provider lockfile
records are removed. The messenger workspace supplies the shared integration test
and lint tools; both CI test workflows run the full core suite from that combined
environment while core lint CI uses only the core checkout. No retained dependency
versions changed. Distribution and SDK API versions are unchanged.

The package verification script now extracts the core source archive into a
directory without the messenger checkout. Normal `uv lock --check` and
`uv sync --locked`, built-in `none` discovery, CLI configuration validation and
Ruff passed there. The messenger-owned environment passed **1,345 product tests**
with 26 warnings, and its verification harness passed **2 tests**. All four source
archives rebuilt into wheels; the isolated core/provider lifecycle and uninstall
matrix and the four all-installed provider-selection checks passed.

Logs: `/tmp/impulse-decouple-product-final.log`,
`/tmp/impulse-decouple-product-final.xml` and
`/tmp/impulse-decouple-packages-final.log`. Source/archive/wheel evidence and
per-command logs: `/tmp/impulse-package-verification-8kv6n4k3`.
Independent core mypy reports only the unchanged nullable user lookup in
`app/im/application.py:559`; log `/tmp/impulse-decouple-mypy.log`. It reports no
missing messenger imports. Workflow syntax and the corresponding Linux commands
were checked locally; hosted CI and Docker execution were not run. No packages
were published.

#### Docker and Helm deployment boundary

The extraction introduced uv dependency management in core's build and CI paths.
Container startup remains `python -m main`, with the same port, configuration/data
paths and volumes. The full-image workflow builds all three provider wheels into
`wheelhouse/` before the Docker build. A plain local Docker build requires that
preparation to support an external messenger; without provider wheels it supports
only the built-in `none` messenger.

The community Helm chart's default deployment can use that full image without
changing its messenger configuration. Its custom-template feature requires a
follow-up: the chart mounts incident/thread templates into the former source
resource directories and removes `messenger.template_files` from the generated
configuration. Extracted providers read packaged defaults, so those implicit
mounts no longer override templates. See the chart's
[volume-mount helpers](https://github.com/eslupmi-community/helm-charts/blob/main/charts/impulse/templates/_helpers.tpl)
and [ConfigMap template](https://github.com/eslupmi-community/helm-charts/blob/main/charts/impulse/templates/configmap.yaml).
This is a source-backed compatibility finding; Docker and Kubernetes execution
have not been performed for the extracted package set.

Existing historical Phase 2–3 evidence above remains unchanged.

No live tenant, hosted consent page, rendered browser, or production rate-limit validation is included in this local package milestone. Mattermost and Telegram retain the previously documented unauthenticated callback-origin behavior. Docker execution is unavailable in this WSL distro because Docker Desktop integration is disabled; a frozen standalone core installation without sibling sources validates the installation path outside Docker. Remote CI and publication are not performed. The full external-provider qualification gate still requires those applicable checks and the deferred characterization work.

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
- Duplicate, missing, and incompatible selected-provider startup failures, without imports of unused providers.

The external-package milestone additionally requires a clean-environment smoke test:

1. Build the Impulse distribution and one provider wheel.
2. Create an empty virtual environment.
3. Install only Impulse and that provider.
4. Run configuration validation.
5. Start Impulse with a fake provider transport or recorded API fixtures.
6. Verify provider templates load from the installed wheel.
7. Verify uninstalling the provider yields an actionable missing-provider error.

## Compatibility and versioning

- Core and messenger distributions share IMPulse release numbers; each provider requires its matching core distribution.
- Messenger libraries have no independent version bumps. Update a library to the target IMPulse version only when that IMPulse release requires library changes.
- Keep the protocol marker `PLUGIN_API_VERSION` separate from distribution versions; discovery requires an exact marker match.
- Add new optional capabilities or methods with defaults; reserve major versions for breaking DTO or semantic changes.
- Keep provider IDs stable because they are persisted in incidents.
- Preserve current built-in YAML fields and environment names through the internal migration.
- Treat template context fields as part of the public plugin API.
- Exact core dependencies enforce matching distribution versions; installed-wheel tests verify that coordinated package set rather than cross-version compatibility.
- Core dependency management stays independent of providers. The messenger workspace owns the editable sibling source override and combined environment required by the full integration suite.

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

The chosen boundary is now implemented locally: IMPulse owns workflow and its public API, while three packages own messaging integrations. Use uv and the installed-package gate to maintain that boundary. Complete the remaining live/callback-security and release qualification before claiming production external-provider conformance or publishing packages.
