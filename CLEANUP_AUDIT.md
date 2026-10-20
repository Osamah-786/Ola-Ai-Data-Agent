# Pre-Phase-7 Cleanup Audit

Initial read-only audit of the working tree and requested documentation. The subsequent structure cleanup moved only the identified scripts and diagrams and updated their paths; no packages were installed, `.env` contents were not read, and no agent, external API, or database operation was run. Findings are candidates for review; nothing was deleted.

## Findings

| Classification | Finding and reason | Affected paths |
|---|---|---|
| **Security Fix** | `execute_code()` calls Python `exec()` with normal builtins. Its docstring warns against untrusted/model-generated code, but there is no sandbox and no in-repository call site. Remove the helper or make a separately isolated, explicit trusted-code feature before exposing it. | `utils/etl_tools.py:220` |
| **Security Fix** | `DatabaseUtil.execute_sql()` accepts arbitrary SQL and commits it; current repository references use schema inspection, not this method. Remove it or enforce a read-only transaction and narrowly defined query interface. | `utils/database.py:84` |
| **Security Fix** | The legacy CLI ETL accepts caller/model-supplied absolute paths and does not use the web service's public-URL/redirect checks. This is separate from the web ETL, which has managed-root containment and bounded URL fetching. Restrict legacy inputs/outputs or clearly disable that entry point for untrusted callers. | `agents/etl_analyst.py:56,113,233`; `utils/etl_tools.py:23,126` |
| **Security Fix** | The SQL validator is lexical/regex-based, not a SQL parser. The workflow adds a read-only transaction, but database-side least-privilege permissions have not been verified. Do not treat the validator or LLM review as authorization; verify a dedicated read-only role and consider parser-based validation before real data use. | `agents/sql_analyst.py:69,291`; `utils/database.py`; `README.md` |
| **Security Fix** | `scripts/database/feed_db.py` connects during module import and executes `TRUNCATE ... CASCADE` on five tables before loading. The README warns about this, but the script has no opt-in destructive-operation guard. Keep it out of routine setup and require an explicit disposable-database guard before anyone runs it. | `scripts/database/feed_db.py:1,228` |
| **Security Fix** | The app has no authentication or owner isolation. ETL datasets and run history are shared among API callers. This is documented and acceptable only for the local single-user scope; add identity-based authorization before multi-user or hosted exposure. | `app/main.py`; `app/api/runs.py`; `app/api/etl.py`; `app/core/run_history.py`; `README.md`; `PROJECT_CONTEXT.md` |
| **Security Fix** | `test_schema_details.txt` is a tracked generated schema-inspection dump; the generator includes sample database rows. Review/sanitize it without publishing any real data. Local `.env` and `frontend/.env.local` files are ignored and were not opened; ensure browser-exposed `VITE_*` variables contain no credentials. | `test_schema_details.txt`; `utils/database.py:48-68,132`; `.gitignore`; `frontend/.env.local` |
| **Remove Candidate** | Experimental scratch module invokes an LLM at import time and has no source call sites. Remove it or convert it to an explicitly guarded test/demo before packaging. | `agents/scratch.py` |
| **Remove Candidate** | Empty root `main.py` duplicates the name of the actual FastAPI entry point and has no content or references. | `main.py`; `app/main.py` |
| **Keep** | Standalone Pokémon transform script remains a documented example under scripts. It performs file operations at import, so execute it only as a CLI; a main guard can be considered separately. | `scripts/examples/transform_pokemon.py`; `agents/etl_analyst.py`; `app/services/etl_transform.py` |
| **Keep** | Generated review/build artifacts remain in place and are now ignored to avoid accidental addition. Remove only after confirming they contain no user data and are no longer needed. `frontend/node_modules/` and `frontend/dist/` are also ignored. | `.phase6-local-review.sqlite3`; `.phase6-*-pytest-tmp/`; `ola_agentic_ai_project.egg-info/`; `.gitignore` |
| **Consolidate** | Two ETL stacks coexist: hardened web services and older agent/utility implementations, with overlapping extraction, file I/O, and transforms. Retain both only with clear supported-use boundaries; otherwise converge on shared safe primitives or retire the legacy path. | `app/services/etl_extraction.py`; `app/services/etl_storage.py`; `app/services/etl_transform.py`; `agents/etl_analyst.py`; `utils/etl_tools.py` |
| **Consolidate** | `README.md`, `PROJECT_CONTEXT.md`, and `BUILD_PLAN.md` repeat capability/status history. Keep README as the user guide, Project Context as a short current-state index, and Build Plan as the canonical phase evidence. README setup text says declared dependencies may be incomplete and separately installs an unpinned package list, although `pyproject.toml` declares the runtime imports; revise that outdated guidance. | `README.md:145-154`; `PROJECT_CONTEXT.md`; `BUILD_PLAN.md`; `pyproject.toml` |
| **Consolidate** | Runtime dependencies inspected appear used; no dependency is clearly removable from static imports. However, backend launch instructions rely on Uvicorn without declaring it in `pyproject.toml`, and Python dependencies have no lockfile. Declare/document the server extra and establish a reproducible Python resolution after compatibility is verified. The frontend lockfile's root declarations match `package.json`, but both are currently untracked. | `pyproject.toml`; `frontend/package.json`; `frontend/package-lock.json`; `README.md` |
| **Keep** | Retain the frontend lockfile and current direct dependencies until a verified dependency audit proves a package is unused. React/Vite/TypeScript, backend imports, PostgreSQL driver, and Parquet support have current code paths. | `frontend/package-lock.json`; `frontend/package.json`; `pyproject.toml` |
| **Consolidate** | Both `.venv/` and legacy `venv/` are present; prior project records report different Python versions, which makes activation and test results ambiguous. Standardize documented development on the supported Python 3.13+ `.venv`; preserve both environments until their ownership and contents are confirmed. | `.venv/`; `venv/`; `README.md`; `BUILD_PLAN.md` |
| **Keep** | Tracked graph PNGs are organized as workflow illustrations. Router and SQL exporters now target the same diagrams directory; no ETL graph exporter was found. | `docs/diagrams/data_agent_graph.png`; `docs/diagrams/etl_analyst_graph.png`; `docs/diagrams/sql_analyst_graph.png`; `agents/data_agent.py`; `agents/sql_analyst.py` |
| **Consolidate** | Git status is substantially dirty: application, tests, roadmap/context, and frontend files are untracked, while `.gitignore`, README, agent files, and `pyproject.toml` are modified. This audit preserved all of them. Confirm the intended source set before staging; ordinary commits omit untracked implementation files unless explicitly added. | Repository working tree (see `git status --short`) |

## Verification gaps by phase

- **Phase 0:** static preparation only; editable installation previously failed in the sandbox, so package-install/build reproducibility remains open.
- **Phase 1:** the existing HTTP test helper stalled; rerun health, metadata, validation, and error tests with Python 3.13 in a stable test environment.
- **Phase 2:** production build is verified, but there is no frontend test runner/interaction suite; run the documented UI states in browser tests.
- **Phase 3:** live graph/Groq paths have not been exercised (appropriately); mock dispatch is covered, but broader HTTP dispatch tests remain blocked by the stalled helper.
- **Phase 4:** mocked extraction/transformation and fixture browser paths passed; actual external-provider behavior is intentionally unverified. Keep those checks isolated and controlled.
- **Phase 5:** fake-agent tests/build passed, but SQL browser interaction and database-side read-only role/permission verification remain open.
- **Phase 6:** local single-user persistence/API checks passed; page data states could not be fetched in the browser in the latest review. Shared history and absent authentication remain deployment blockers.

## Five highest-value improvements before deployment

1. Add authentication and per-user authorization for runs, datasets, and every state-changing or data-bearing endpoint.
2. Remove or isolate arbitrary `exec`, arbitrary committed SQL utilities, and legacy ETL path/URL access; add regression tests around the boundaries.
3. Make `feed_db.py` non-destructive by default and require explicit confirmation/guarding for any truncate-and-load workflow; remove or sanitize the tracked sample-data dump.
4. Verify and enforce a least-privilege PostgreSQL role, strengthen SQL validation beyond regex, and keep read-only transaction/timeouts as defense in depth.
5. Establish CI with Python 3.13 install/build plus complete mocked backend tests, frontend interaction tests, and browser route/error/success coverage; resolve the HTTP test-helper stall first.

## Audit limits

This is static inspection, not a penetration test, dependency vulnerability scan, secrets scan, or production database review. `scripts/database/feed_db.py`, agent graph exporters, LLM clients, external URLs, and PostgreSQL were not executed. `.env` files were not read. No package installation or destructive cleanup was performed.

## Repository structure cleanup record — 2026-10-20

### Resulting layout

- Kept `app/`, `agents/`, `models/`, and `utils/` as separate Python packages; frontend, tests, data, and app data retain their existing roots.
- Moved `feed_db.py` to `scripts/database/feed_db.py` and anchored its CSV path to the project root. Moved `transform_pokemon.py` to `scripts/examples/transform_pokemon.py` and anchored its input/output paths to the project root.
- Moved the three tracked graph PNGs into `docs/diagrams/`; adjusted the router and SQL graph output paths. No ETL graph writer was found.
- Updated README references and commands, and added ignore patterns for generated root datasets, Phase 6 review artifacts, and project egg-info. Existing generated files were not deleted or relocated.

### Verification and remaining items

- `ast.parse` syntax checks passed for the moved scripts and edited graph-writing modules. Static repository searches found no stale root script/image references. `git diff --check` passed.
- Tests and `npm run build` were not run: this cleanup was limited to paths/docs and no dependencies were installed; a production build is not material to path-only changes. No external API, LLM, agent, PostgreSQL, or `feed_db.py` operation occurred.
- `test_schema_details.txt` remains tracked at its original location and was not read or moved because the audit identifies it as a generated schema dump containing sample rows. Treat it as potentially sensitive and review/sanitize it before sharing. The loader still has import-time database side effects and destructive truncate behavior.
- The existing working tree contains many pre-existing user changes and untracked project files; all were preserved. No staging or cleanup deletion was performed. `CLEANUP_AUDIT.md` itself remains a user-created untracked document in the current repository state.
