# Ola AI Data Agent — Product Blueprint and Canonical Roadmap

## Product vision

Turn the existing Python agent workflows into a browser-based data workspace. Users will describe data tasks in plain English, operate an ETL experience for supported API and file operations, and ask natural-language questions about PostgreSQL through a SQL analyst experience.

The application is planned; it is not currently a hosted web app. See [README.md](README.md) for verified current capabilities and limitations.

Before Phase 7, review the read-only repository findings in [CLEANUP_AUDIT.md](CLEANUP_AUDIT.md). The audit does not authorize cleanup or code changes.

## Intended architecture

- **Frontend:** React, TypeScript, and Vite. A unified workspace will surface task input, status, errors, results, and relevant output metadata, with focused ETL and SQL experiences.
- **Backend:** Python and FastAPI. It will validate requests, expose health and metadata, and call existing agent workflows through controlled service boundaries.
- **Agent orchestration:** The existing LangGraph router will classify a user task as ETL or SQL and delegate to the corresponding workflow, once controlled integration is implemented.
- **LLM integration:** Existing LangChain and Groq configuration will support routing, ETL planning, SQL generation, safety review, and response summaries.
- **Database:** Existing PostgreSQL integration will support SQL analysis. Use a dedicated least-privilege read-only database role; model review is not a security boundary.
- **File storage:** Web-managed generated artifacts will be stored under `app_data/generated/`, with server-side path containment, preview limits, and controlled downloads. Existing command-line examples and workflows currently use `data/`; they will remain as legacy behavior until a later phase safely integrates them.
- **Testing and operations:** Python and frontend tests should use mocks where possible. Later work includes structured logs, timeouts, rate limits, deployment, and security hardening.

## User experiences

1. **Unified workspace:** Submit a natural-language task, see the selected operation, progress/status, result, or error.
2. **ETL Studio:** Fetch supported APIs, choose output format, transform datasets using natural-language instructions, preview results, and download generated files.
3. **SQL Analyst:** Ask questions about PostgreSQL, inspect safety status and tabular results, and receive a plain-English explanation.
4. **Optional run history:** Persist and browse operation metadata only if later requirements justify it; it is not required for the initial application.

Settings, schema browsing, and other supporting views may be added as they are needed by these experiences. Secrets must remain server-side and must not be exposed in browser configuration.

## Proposed API contract

The following endpoints are **proposed** and do not exist in the current repository. Phase 1 may refine request/response schemas and execution behavior before they are considered implemented.

| Endpoint | Method | Proposed purpose |
|---|---|---|
| `/health` | GET | Liveness/readiness response. |
| `/metadata` | GET | Version and supported capability metadata. |
| `/etl/run` | POST | Validate and start a controlled ETL operation; return an operation identifier and status. |
| `/etl/status/{task_id}` | GET | Return status and, when complete, result metadata for an ETL operation. |
| `/sql/run` | POST | Validate a natural-language question and run the SQL analyst; return safety information, bounded rows, and explanation. |

An endpoint is implemented only when source code and appropriate verification confirm it; documentation of this proposal is not evidence of implementation. The API exposes `GET /api/health`, `GET /api/metadata`, and `POST /api/agent/run`; agent-run requests default to mock mode, while explicit live requests are guarded by `ENABLE_LIVE_AGENTS`. The unprefixed paths above and the remaining ETL/SQL task routes are still proposals.

## Security and reliability requirements

- Preserve the SQL workflow's deterministic validation, structured safety review, pre-execution validation, read-only transaction, timeout, and bounded result behavior.
- Enforce database read-only access with a restricted PostgreSQL role and database permissions. An LLM approval is never sufficient authorization.
- Constrain web-managed output paths to `app_data/generated/`; reject traversal and arbitrary absolute paths. Enforce file-size, preview, and download limits.
- Validate request data with Pydantic, keep secrets server-side, and define rate limits and timeouts for external calls.
- Do not route untrusted or model-generated content to the legacy arbitrary `exec` helper.
- Add security and failure tests before exposing the application to real data.

## Canonical implementation roadmap

Complete phases in order. Acceptance criteria describe what must be true before a phase is considered complete; they do not claim that the work already exists.

### Phase 0 — Project Preparation (complete: static checks only)

- Align direct third-party imports with project dependency declarations without unsupported version upgrades.
- Provide a placeholder-only `.env.example`; ensure secrets and generated/runtime data are ignored by Git.
- Reconcile project documentation around this canonical plan and identify proposed endpoints as proposed.
- Static inspection confirms configuration and documentation consistency. Installation, application startup, and runtime import checks are deferred because they can invoke code or require external state.
- **Completion evidence:** checked-in declarations and ignore rules inspected; no secrets or generated outputs tracked; agent workflow source unchanged. No installation or runtime test is claimed.

### Phase 1 — FastAPI foundation

- Add a FastAPI application with health and metadata endpoints, request/response schemas, configuration loading, and structured error responses.
- Establish service boundaries and dependency injection without exposing arbitrary file paths or database credentials.
- **Acceptance:** API contract is documented and validated; health/metadata tests pass with external services mocked; agent workflows are not invoked by liveness checks.

### Phase 2 — React foundation and workspace

- Create a React + TypeScript + Vite frontend with shared layout, navigation, task input, result/status/error display, and responsive styling.
- Connect only to the backend API contract; do not embed secrets in frontend assets.
- **Acceptance:** frontend builds and its UI tests use mocked API responses; loading, success, empty, and error states are represented.

#### Phase 2 implementation record

The Vite/React/TypeScript source, shared shell, Workspace, typed API client, connection indicator, and ETL/SQL pages have been added. The production build has been verified. Later browser review confirmed workspace and route rendering, navigation, a mock Workspace request, backend health status, and the ETL page at a 304px viewport without page-level horizontal overflow. There is still no frontend test runner or DOM test setup, so Phase 2 remains incomplete until the required UI tests are added and pass.

#### Phase 2 dependency verification update — 2026-10-18

Frontend installation was previously blocked before package resolution. In `frontend/`, Node reported `v24.15.0`, npm reported `11.12.1`, and the configured registry was `https://registry.npmjs.org/`. `npm ping` failed with `ENOTFOUND` while resolving `registry.npmjs.org`; no proxy is configured. The npm debug-log path was inaccessible from the shell, so the underlying DNS/network condition could not be further isolated. Subsequent supplied terminal results confirm `tsc --noEmit` and the Vite production build passed; Vite transformed 27 modules and generated production assets in `frontend/dist/`. Installation/lockfile status remains as previously reported for that attempt: it created no lockfile or `node_modules/`. A later Phase 4 browser session verified navigation, mock Workspace communication, configured backend health, ETL URL feedback/server rejection, fixture-backed preview rendering, and narrow viewport layout. Frontend interaction tests remain unverified because no frontend test setup exists. Phase 2 remains incomplete.

### Phase 3 — Controlled agent integration

- Integrate the existing LangGraph router and ETL/SQL workflows behind backend services with validated inputs, bounded execution, and normalized outputs.
- Define operation lifecycle and error behavior; do not claim background task progress unless the implementation actually reports it.
- **Acceptance:** mocked service/API tests cover routing, failures, and response mapping; file and SQL safety boundaries are enforced before real integrations are enabled.

#### Phase 3 implementation and verification record

The API now accepts `execution_mode` (`mock` by default or explicit `live`). Mock requests return a deterministic response without importing agent modules. Live dispatch requires `ENABLE_LIVE_AGENTS=true` in the server process and an individual `live` request; otherwise the API rejects it with HTTP 403. The existing `agents.data_agent` graph is loaded lazily only after both gates pass. Its existing input contract (`messages` with a `HumanMessage` and initialized `route_response`) is used, and the returned route and latest useful AI message are normalized. Agent failures and unusable results map to controlled HTTP errors.

The Workspace now exposes a mock-default selector, warns about Groq/API/PostgreSQL effects in live mode, sends the selected mode, and displays server live-mode availability. Focused backend tests for both gates, mocked graph dispatch/result extraction, errors, and startup endpoints were added. `python -m compileall -q app tests/unit/test_api.py` passed. A direct API-handler/service smoke check passed with an injected fake graph. The frontend `npm run build` passed (`tsc --noEmit`, Vite transformed 27 modules, and assets were emitted in `frontend/dist/`). However, `python -m pytest -q` could not run because `pytest` is not installed; the available Python is 3.12.10 while the project requires 3.13 or later. The in-process HTTP smoke request stalled on `/api/health`, and the attempted local Uvicorn check was not reachable, so HTTP dispatch/startup remains unverified. The frontend has no test script, Vitest, or DOM testing dependencies, and browser interaction is unverified. No live graph, Groq, ETL/SQL workflow, external API, or PostgreSQL request was performed. Therefore Phase 3 is not marked complete; run the added mocked backend tests and add/run frontend interaction tests in a compatible environment before considering acceptance.

### Phase 4 — ETL functionality (complete: mocked backend checks, local HTTP safety path, frontend build, and browser review)

- Build ETL Studio API/UI flows for supported extraction, transformation, format selection, managed previews, and downloads.
- Store web-generated outputs under `app_data/generated/` and enforce path containment and size limits.
- **Acceptance:** mocked tests cover validation and operation outcomes; preview and download access cannot escape the managed storage root.

#### Phase 4 implementation and verification record — 2026-10-20

The ETL Studio replaces the `/etl` placeholder and uses the shared typed API client. The backend exposes `POST /api/etl/extract`, `POST /api/etl/transform`, `GET /api/files`, `GET /api/files/{file_id}/preview`, and `GET /api/files/{file_id}/download`. Extractions support JSON arrays, single JSON objects, and `results`/`next` pagination. Supported output formats are CSV, JSON Lines (`json`), and Parquet. Extraction has bounded timeouts, redirects, pages, per-response and aggregate response bytes, records, and stored dataset size. URL validation rejects credentials, local/private/reserved destinations, unsafe schemes, unsafe DNS results, and every redirect destination before following it.

Web outputs are stored under the documented `app_data/generated/extracts/<uuid>/` and `app_data/generated/transforms/<uuid>/` layout. A validated, atomically replaced `manifest.json` persists identifiers and safe metadata across server restarts. Paths are reconstructed only from server-created manifest entries, resolved, and checked to remain under the managed root. Preview pagination defaults to 20 and is bounded to 100 rows per request. Downloads use generated IDs and safe filenames; no filesystem path is accepted or returned.

Extraction is LLM-free and does not import the ETL agent. Transformation defaults to mock and returns HTTP 409 without writing a dataset. An actual planner is invoked only for an explicit `execution_mode: "live"` request after `ENABLE_LIVE_AGENTS=true` is confirmed on the server. The planner uses the existing Groq-backed ETL planner, but deterministic parsing and constrained pandas plan application are now shared in `app/services/etl_transform.py`; arbitrary generated Python is never executed. A successful operation creates a new dataset; an empty plan is rejected by the web API without an output file. The legacy CLI agent keeps its existing no-operation result behavior.

Verification performed:

- `.venv` Python 3.13.11: `python -m pytest -q --basetemp .phase4-pytest-tmp tests\\unit\\test_etl_api.py` — 22 passed. The suite uses mocked DNS and HTTP, temporary managed storage, and fake planners. It covers URL/redirect/HTTP/JSON failures, repeated and bounded pagination, per-response and aggregate byte limits, record bounds, confirms extraction does not import agent/Groq modules, verifies mock/live gates and no-op rejection, exercises constrained plans, all three file formats, preview/download behavior, manifest persistence/path containment, and route/schema registration.
- `npm run build` in `frontend/` — passed; TypeScript check passed and Vite transformed 29 modules and emitted production assets.
- `python -m compileall -q app\\services app\\api\\etl.py app\\models\\etl.py agents\\etl_analyst.py tests\\unit\\test_etl_api.py` and `git diff --check` — passed. Git printed only existing LF-to-CRLF working-copy warnings.
- Browser review at `http://127.0.0.1:5173/etl`: backend health/metadata/list calls connected; navigation between ETL, Workspace, and SQL worked; choosing an example populated the URL without submitting; `ftp:` validation appeared and disabled extraction; submitting `https://localhost/private-test` returned the backend's safe rejection before DNS or HTTP access. Workspace example selection and an explicit mock request rendered the deterministic backend mock response. A separate temporary local server replaced only the extraction service with a deterministic fixture (the submitted Pokémon URL was ignored); the page rendered success metadata, a managed dataset selection, preview cells with null/date/nested values, and download links. Mock transformation displayed an explicit no-output message. No browser download click or actual extraction/live transformation was performed.
- A narrow 304px browser viewport showed no page-level horizontal overflow after reducing the minimum page width and allowing the header to wrap. The sidebar uses its own horizontal navigation scroller.
- No frontend test runner or DOM testing dependencies exist in `frontend/package.json`; no frontend test infrastructure was added. Browser success rendering and preview content were checked with the local fixture; browser pagination interaction and an actual download click remain unverified. Their server-side behavior is covered by mocked tests and their frontend is build-checked.
- The extraction and transformation buttons now show loading text only for their active operation; the concurrent misleading loading labels found during the fixture browser check were corrected and the final frontend build passed.
- The pre-existing Phase 3 `tests\\unit\\test_api.py` suite was separately attempted and stalled on its first in-process ASGI request (`test_health_returns_expected_structure`) without emitting a result. It was stopped; the new ETL suite avoids that helper and passed. Direct local HTTP health, metadata, managed-file listing, and the ETL validation error path were exercised in the browser. This does not resolve the pre-existing broader Phase 1–3 automated HTTP-dispatch blocker.

No real external API was requested, and no Groq/LLM, LangGraph workflow, PostgreSQL, or `feed_db.py` operation occurred. Live transformation remains disabled unless a developer explicitly enables the existing server gate and a request explicitly selects live mode. Phase 5 SQL implementation and verification status are recorded below; it remains incomplete.

Phase 4 acceptance is marked complete for the implemented mock-safe ETL Studio, using mocked service tests and the local HTTP/browser verification described above. Browser success rendering used a temporary fixture that made no external request. Live provider behavior remains intentionally unverified.

### Phase 5 — SQL Analyst interface

- Build the SQL question UI with safety status, bounded tabular results, and a plain-English explanation.
- Preserve existing SQL safety checks and require restrictive database permissions in configuration and deployment guidance.
- **Acceptance:** mocked tests cover safe, rejected, empty, and failed query outcomes; database-side read-only permissions are documented and verified in a controlled environment before real data use.

#### Phase 5 implementation and verification record — 2026-10-20

The `/sql` placeholder is replaced with a natural-language SQL Analyst page. It includes example questions, mock-default and explicit live request controls, request loading/errors, generated SQL, safety status and rejection reason, answer text, row count, and a horizontally contained results table. The typed frontend client calls `POST /api/sql/run`. The FastAPI request is limited to a nonblank 4,000-character natural-language question; there is no arbitrary-SQL request field. The response is typed and capped at 100 rows.

`SqlAnalystService` returns a clearly identified mock response without importing the agent. Live execution is considered only for an explicit `execution_mode: "live"` request after the existing `ENABLE_LIVE_AGENTS=true` server gate passes. The existing SQL graph is loaded lazily and retains its deterministic validation, structured safety review, final validation, read-only transaction, statement timeout, and row bound. Its bounded rows are serialized as JSON (with non-JSON scalar values converted to displayable text) for the typed API adapter. A rejected candidate/final validation is surfaced as rejected with its reason; execution errors are returned without exposing database exception details. README guidance requires a dedicated PostgreSQL role with only required `SELECT` permissions and prohibits using owner/superuser credentials.

Verification performed:

- `.venv\Scripts\python.exe -m pytest -q --basetemp .phase5-pytest-tmp tests\unit\test_sql_api.py` — 8 passed. Tests use an injected fake graph only and cover mock no-load behavior, disabled-live rejection before loading, safe rows/answer, safety rejection and reason, empty results, final-validation rejection, JSON row values, and controlled execution failure. No real SQL graph was imported or invoked.
- `npm run build` in `frontend/` — passed: `tsc --noEmit` and Vite v8.3.4 production build; 29 modules transformed and assets emitted.
- `git diff --check` — passed; only existing line-ending conversion warnings were printed.
- FastAPI OpenAPI schema generation confirmed `/api/sql/run` is registered.
- A local browser attempt at `/sql` timed out. A local HTTP probe was denied socket access by the execution environment, so browser rendering, interaction, and responsive behavior remain unverified. The temporary development servers were stopped. No frontend interaction-test runner is configured, and no such tests were run.
- No PostgreSQL role or database permissions were inspected or verified in a controlled environment. The README documents the required least-privilege setup; documentation is not database-side verification.

Phase 5 is **not complete**: the controlled database permission verification acceptance criterion remains outstanding, and browser/UI interaction checks were blocked. Phases 1–3 also retain their previously documented runtime verification blockers. No live LLM, SQL/ETL/LangGraph agent, external data API, PostgreSQL, or `feed_db.py` operation occurred.

#### Phase 5 focused re-verification — 2026-10-20

- `.venv\Scripts\python.exe -m pytest -q --basetemp .phase5-review-pytest-tmp tests\unit\test_sql_api.py` — 9 passed. The suite covers request/schema mock default, no graph load in mock mode, live rejection before loader invocation when the server gate is disabled, fake safe/rejected/empty/failure outcomes, result rows, and controlled error reporting.
- `npm run build` from `frontend/` — passed: `tsc --noEmit`, Vite 8.3.4, 29 modules transformed.
- SQL safety review confirmed the API accepts only a natural-language question, mock is the request default, live execution checks both gates before lazy loading, and the existing workflow has deterministic SQL checks, a read-only transaction, a 15-second timeout, and a 100-row bound. The validator is a basic lexical check, not a complete SQL parser; least-privilege database permissions remain an independent requirement.
- No frontend test setup is installed (Vitest, React Testing Library, and DOM environment are absent), so no new test dependencies were added. The earlier browser timeout/socket restriction remains; SQL-page interaction and responsive layout were not verified in a browser.
- No PostgreSQL connection, database-role/permission inspection, live graph, LLM, or external service was used. The database-side least-privilege check and browser verification remain open; Phase 5 stays incomplete.

### Phase 6 — Optional run history

- Add history only if product requirements call for it, including retention, access control, and deletion behavior.
- **Acceptance:** if implemented, tests verify ownership/access boundaries and retention rules. This phase may be explicitly deferred without blocking the initial product.

#### Phase 6 implementation and verification record — 2026-10-20

SQLite run history is implemented in `app/core/run_history.py`, with `GET /api/runs` and `GET /api/runs/{run_id}`. Existing Workspace agent, ETL extraction/transformation, and SQL endpoints record completed and failed/rejected outcomes without changing their response payloads. The database is created lazily at `app_data/run_history.sqlite3` (overridable with `RUN_HISTORY_DB_PATH`); each operation uses a separate SQLite connection, and only the most recent 500 runs are retained. Dataset IDs are recorded for successful ETL creation/transformation.

History stores fixed generic task labels and summaries only. It does not accept or persist raw prompts, ETL URLs/instructions, generated SQL, database rows/answers, or exception details. The history API is read-only; unknown IDs return 404. No user identity/authentication exists in this application, so records are shared by all callers able to reach this local API. This is not owner isolation and must be addressed before multi-user/hosted deployment.

Verification performed:

- `.venv\Scripts\python.exe -m pytest -q --basetemp .phase6-pytest-tmp tests\unit\test_sql_api.py tests\unit\test_etl_api.py tests\unit\test_run_history.py` — 38 passed. Coverage includes persistence across store instances, success/failure outcomes for Workspace/ETL/SQL handlers with fake services, empty dataset output behavior, unknown run IDs, bounded retention, dataset ID links, and checks that prompt/URL/answer/result details are not stored. The SQL and ETL suites use mocks and fixtures.
- `npm run build` in `frontend/` — passed with TypeScript and Vite; 30 modules transformed.
- `python -m compileall -q` over the changed backend modules/tests and `git diff --check` passed (the latter emitted existing LF-to-CRLF working-copy warnings).
- The Run History screen provides loading, empty, error, recent-run, detail, and dataset-download-link states. No frontend interaction test runner is installed and no browser check was performed in this phase.
- No real agent, LLM, external API, PostgreSQL, or feed script was used.

Phase 6 is complete for the verified **local single-user scope only**. Run history is shared by every caller of this API, and authentication/authorization is absent; it is not suitable for multi-user or hosted exposure until identity-based access control is implemented. No history deletion UI or endpoint was added; records expire by the 500-run retention cap.

#### Phase 6 local single-user re-verification — 2026-10-20

- Started the local FastAPI service with `RUN_HISTORY_DB_PATH` set to the temporary `.phase6-local-review.sqlite3` file and `ENABLE_LIVE_AGENTS=false`. `GET /api/health` returned 200 in mock mode and the initially empty `GET /api/runs` returned 200 with `[]`.
- Submitted a deterministic `execution_mode: mock` Workspace request using a private sentinel prompt; it returned 200. Submitted an explicit `execution_mode: live` request while the server gate was false; it was rejected with 403. Neither request invoked agent code. Run listing exposed only generic task labels, workflow/mode/status, timestamps, generic summary, and dataset IDs. The private prompt sentinel and a separate blocked-request sentinel were absent from list/detail JSON and SQLite content. No SQL, database rows, credentials, or exception details were present in history responses.
- Restarted FastAPI against the same SQLite file. `GET /api/runs` returned 200 with both success and failed records still present; the detail endpoint returned 200 for a listed ID, and an unknown ID returned 404. API response fields were exactly `run_id`, `task_description`, `workflow`, `execution_mode`, `status`, `started_at`, `completed_at`, `result_summary`, and `dataset_ids`.
- `.venv\\Scripts\\python.exe -m pytest -q --basetemp .phase6-review-pytest-tmp tests\\unit\\test_sql_api.py tests\\unit\\test_etl_api.py tests\\unit\\test_run_history.py` — **38 passed**.
- `npm run build` from `frontend/` — **passed**; `tsc --noEmit`, Vite transformed 30 modules and emitted production assets.
- Browser review at `http://127.0.0.1:5173/` confirmed Workspace and visible navigation; clicking Run History navigated to `/history`. The page visibly displayed its backend connection error state. Although direct browser navigation to `http://127.0.0.1:8000/api/health` returned the mock health JSON and local HTTP history checks passed, the frontend page's API fetches still reported a connection failure. Therefore the browser's empty/list/detail/status rendering was **not** verified; those API outcomes are covered by the mocked tests and direct local HTTP checks. No responsive viewport check was completed.
- History data remains **shared and unauthenticated**. Completion applies only to this local single-user verification, not concurrent users, tenant isolation, or hosted deployment. No live AI, LangGraph agent, external data API, PostgreSQL, or `feed_db.py` operation occurred.

### Phase 7 — Testing, deployment, and security hardening

- Complete Python and frontend test coverage using mocks where possible; add integration/security checks that require services only in a controlled environment.
- Add deployment assets and CI for linting, type checking, and tests; review secrets, permissions, timeouts, rate limiting, logging, and failure recovery.
- **Acceptance:** CI checks pass; deployment and rollback instructions exist; external-service checks are identified separately from mocked tests; security review findings are recorded and addressed or explicitly accepted.

#### Phase 1 implementation record

The FastAPI skeleton and focused API tests have been added. Runtime verification is incomplete: the available virtual environment uses Python 3.11.9 while the project declares Python 3.13 or later, pytest is not installed, and the installed FastAPI/Starlette TestClient smoke request did not complete. Direct application import and service/schema checks passed, but HTTP dispatch and the automated suite remain unverified. Phase 1 acceptance is therefore not yet marked complete; run the test suite in a compatible environment before proceeding.

#### Runtime verification update — 2026-10-20

`py -0p` reported no installed Python runtimes, `python --version` reported 3.12.10, and the existing `venv/` Python reported 3.11.9; both are below the declared `>=3.13` requirement. The existing `venv/` was preserved; no new virtual environment was created. Per the verification prerequisite, dependency installation, pytest, server startup, and HTTP requests were stopped before execution. The declared test dependencies are `httpx` and `pytest` in the `dev` group. Node `v24.15.0`, npm `11.12.1`, `frontend/node_modules/`, and `frontend/package-lock.json` are present, but this attempt did not rerun the frontend build or browser checks. Prior build and direct mocked handler/service checks remain documented above; real HTTP dispatch is still unverified. Phases 1–3 remain incomplete.

#### Packaging correction and verification attempt — 2026-10-20

The project used setuptools' implicit build backend without an explicit package-discovery configuration. Flat-layout discovery treated unrelated top-level directories (`frontend`, `data`, and `tests`) as packages and failed. The actual backend package layout is `app` (regular package) plus `agents`, `models`, and `utils` (implicit namespace packages). `pyproject.toml` now declares `setuptools.build_meta` and explicitly includes those backend packages while excluding frontend, data, tests, virtual environments, build outputs, and caches. The Python requirement, runtime dependencies, and `dev` dependency group are unchanged.

For this attempt, the project `.venv` interpreter was Python 3.13.11; the shell default remained 3.12.10 and the existing `venv/` remained Python 3.11.9. The requested `python -m pip install -e . --group dev` was run with `.venv` Python 3.13.11 and failed with exit code 1: `OSError: [Errno 13] Permission denied` while accessing pip's sandbox-managed temporary `pip-build-tracker` directory. Installation did not complete, so pytest, backend HTTP checks, and frontend rebuild/browser checks were not run after this packaging change. The explicit package configuration has not yet been validated by a successful build/install. Phases 1–3 remain incomplete.

## Phase 0 status record

Phase 0 was completed through static repository checks on 2026-10-18. Dependency declarations, environment-variable names, ignore rules, Git tracking status, and documentation were inspected. `.env` was not read. No dependency installation, application startup, agent invocation, external API request, or database connection was performed. Runtime compatibility and installation therefore remain unverified.

## Repository structure cleanup — 2026-10-20

- Moved the standalone loader to `scripts/database/feed_db.py` and the Pokémon transform example to `scripts/examples/transform_pokemon.py`; both resolve data paths from the repository root. Loader execution was not performed because it connects to PostgreSQL and truncates tables.
- Moved tracked workflow diagrams to `docs/diagrams/`; router and SQL graph exporters now write there and create the target directory as needed. No agent was invoked to regenerate diagrams.
- Added ignore patterns for root generated dataset folders, Phase 6 local review databases/temp dirs, and project egg-info. Existing local/generated artifacts were preserved.
- Updated README commands/layout and this context record. The tracked `test_schema_details.txt` was not opened, moved, or sanitized; review its database sample contents before sharing.
- Static path/reference and Python syntax checks are recorded in `CLEANUP_AUDIT.md`. Mocked backend tests and frontend build were not run because this cleanup was limited to moved backend scripts, graph-output paths, and documentation; dependencies were not installed. The `.venv` Python 3.13.11 was used only for `ast.parse`. No live services or database were contacted.

## Phase 7 Step 1 — security fixes

The tracked schema sample dump was removed from the working tree and ignored; no Git history was rewritten. Database schema context now contains metadata only, the generic committing SQL utility and Python `exec()` helper were removed, and legacy ETL HTTP/path handling was bounded and restricted. The database loader now has a main guard and requires `--confirm-truncate` before environment loading or connection. `.venv\Scripts\python.exe -m pytest -q --basetemp .phase7-security-pytest-tmp tests/unit/test_legacy_security.py tests/unit/test_etl_api.py tests/unit/test_sql_api.py` passed (**51 passed**); compileall and `git diff --check` also passed. All network and database behavior in the focused tests was mocked; no live agent, external API, or PostgreSQL was used. This record does not begin or complete Phase 7 Steps 2–6.
