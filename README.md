
# Ola AI Data Agent

Ola AI Data Agent is a local learning project for exploring API datasets and asking questions about PostgreSQL data. It includes a FastAPI backend, a React + TypeScript frontend, and existing LangGraph workflows for ETL and SQL analysis.

The web application is **mock-first**. Live agent work is disabled unless the backend is explicitly configured to allow it and a request explicitly selects live mode. Review the safety notes below before enabling live execution.

## Features

- **Workspace** (`/`): submit a natural-language data request and inspect the response.
- **ETL Studio** (`/etl`): explicitly fetch data from a supplied API URL, preview managed datasets, download them, and use mock or explicitly gated AI-assisted transformation.
- **SQL Analyst** (`/sql`): submit a natural-language database question. Mock mode is the default; live mode requires both the request selection and the server gate.
- **Run History** (`/history`): view privacy-minimized run records persisted in SQLite under `app_data/`.
- **Backend API**: FastAPI routes provide health/metadata, agent, ETL, SQL, dataset, and run-history operations.

## Repository layout

```text
ola_agentic_ai_project/
├── app/                      # FastAPI application, API routes, services, and models
├── agents/                   # Existing LangGraph workflows
├── models/                   # Shared agent schemas
├── utils/                    # Shared utilities
├── frontend/                 # React + TypeScript + Vite application
├── tests/unit/               # Mocked backend tests
├── scripts/
│   ├── database/feed_db.py   # Destructive sample database loader
│   └── examples/              # Standalone examples
├── docs/diagrams/            # Workflow graph images
├── data/                     # Local input data; Git-ignored
├── app_data/                 # Managed outputs and run-history database; Git-ignored
├── BUILD_PLAN.md             # Roadmap and verification record
├── PROJECT_CONTEXT.md        # Current project architecture and context
├── CLEANUP_AUDIT.md           # Cleanup/security findings and unresolved items
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.13 or later (`pyproject.toml` requirement)
- Node.js 20.19 or later for the frontend (Node.js 24.15 is used by the project)
- PostgreSQL only for explicitly enabled live SQL workflows or the database loader
- A Groq API key only for explicitly enabled live agent workflows

## Backend setup

From the project root, create and activate a Python 3.13+ virtual environment. In PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
python -m pip install -e . --group dev
```

The development dependency group includes pytest and httpx. The project does not currently declare an ASGI server package in `pyproject.toml`; install/configure one (such as Uvicorn) in the environment before launching the API if it is not already available. For example, after activating `.venv`:

```powershell
python -m pip install uvicorn
python -m uvicorn app.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`. Health and interactive API documentation are available at `/api/health` and `/docs` respectively.

To run the mocked backend tests:

```powershell
python -m pytest -q
```

Tests should use mocked services and must not require live model/API calls or a database connection.

## Frontend setup

In another terminal, from the project root:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite (normally `http://127.0.0.1:5173`). To run the production type-check and build:

```powershell
npm run build
```

To run frontend unit tests:

```powershell
npm test
```

If the frontend needs a different API address, configure `VITE_API_BASE_URL` using `frontend/.env.example` as a reference. This is a browser-visible URL setting; never put credentials or API keys in `VITE_*` variables.

## Live execution and data safety

Keep live execution disabled for ordinary local development. The backend gate is controlled by `ENABLE_LIVE_AGENTS`; the request must also explicitly specify `execution_mode: "live"`. Setting the server variable alone does not make mock requests live. If the gate is disabled, live requests should be rejected; the application must not silently fall back to mock mode.

For a local PowerShell session, explicitly disable the gate with:

```powershell
$env:ENABLE_LIVE_AGENTS = "false"
```

Enabling live execution can call Groq and may execute the selected agent workflow. Only enable it when credentials, network access, data handling, and database permissions have been deliberately configured. Do not commit `.env` files or expose credentials in frontend configuration.

ETL extraction contacts the URL explicitly submitted by the user. Use only trusted endpoints and review downloaded data. Mock transformation does not perform a real transformation or create a dataset.

The SQL agent is intended to use read-only SQL checks and a read-only transaction, but these controls are not a substitute for database-side permissions. Verify a dedicated least-privilege PostgreSQL role before live use. Do not expose the application to multiple users: authentication and per-user isolation are not implemented, and run history and managed datasets are shared by API callers.

### Destructive database loader

`scripts/database/feed_db.py` loads the sample rideshare CSV files from `data/`. It contains `TRUNCATE ... CASCADE` operations and connects to PostgreSQL as part of its execution. It can delete existing data in its target tables. **Do not run it against a database with data you need to keep.** Use only a disposable database after reviewing the script and its configuration. It is intentionally not part of the normal setup steps.

### Local transform example

From the repository root, `python scripts/examples/transform_pokemon.py` reads `data/extract/extracted_data.csv` and writes `data/transformed/transformed_data.csv`. It refuses to overwrite an existing output file. This example does not fetch data itself.

## Generated data and local artifacts

Local input datasets belong under `data/`. The web application stores managed outputs, metadata, and its SQLite run-history database under `app_data/`. These paths and local environments/build outputs are Git-ignored. Do not put credentials, customer data, or sensitive database samples in tracked files.

The tracked `test_schema_details.txt` is a generated schema-inspection artifact and may contain database sample rows. It has not been reviewed as part of the repository cleanup. Treat it as potentially sensitive and inspect/sanitize it before sharing the repository.

## Current verification status

This project is still in development. Some mocked backend checks and frontend builds are documented in `BUILD_PLAN.md`; live LangGraph/Groq execution, external-provider behavior, database permission verification, and complete browser coverage remain unverified. Read the phase status and blockers in `BUILD_PLAN.md` and the security findings in `CLEANUP_AUDIT.md` before relying on the application.
=======
# Ola AI Data Agent

Ola AI Data Agent is a local learning project for exploring API datasets and asking questions about PostgreSQL data. It includes a FastAPI backend, a React + TypeScript frontend, and existing LangGraph workflows for ETL and SQL analysis.

The web application is **mock-first**. Live agent work is disabled unless the backend is explicitly configured to allow it and a request explicitly selects live mode. Review the safety notes below before enabling live execution.

## Features

- **Workspace** (`/`): submit a natural-language data request and inspect the response.
- **ETL Studio** (`/etl`): explicitly fetch data from a supplied API URL, preview managed datasets, download them, and use mock or explicitly gated AI-assisted transformation.
- **SQL Analyst** (`/sql`): submit a natural-language database question. Mock mode is the default; live mode requires both the request selection and the server gate.
- **Run History** (`/history`): view privacy-minimized run records persisted in SQLite under `app_data/`.
- **Backend API**: FastAPI routes provide health/metadata, agent, ETL, SQL, dataset, and run-history operations.

## Repository layout

```text
ola_agentic_ai_project/
├── app/                      # FastAPI application, API routes, services, and models
├── agents/                   # Existing LangGraph workflows
├── models/                   # Shared agent schemas
├── utils/                    # Shared utilities
├── frontend/                 # React + TypeScript + Vite application
├── tests/unit/               # Mocked backend tests
├── scripts/
│   ├── database/feed_db.py   # Destructive sample database loader
│   └── examples/              # Standalone examples
├── docs/diagrams/            # Workflow graph images
├── data/                     # Local input data; Git-ignored
├── app_data/                 # Managed outputs and run-history database; Git-ignored
├── BUILD_PLAN.md             # Roadmap and verification record
├── PROJECT_CONTEXT.md        # Current project architecture and context
├── CLEANUP_AUDIT.md           # Cleanup/security findings and unresolved items
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.13 or later (`pyproject.toml` requirement)
- Node.js 20.19 or later for the frontend (Node.js 24.15 is used by the project)
- PostgreSQL only for explicitly enabled live SQL workflows or the database loader
- A Groq API key only for explicitly enabled live agent workflows

## Backend setup

From the project root, create and activate a Python 3.13+ virtual environment. In PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
python -m pip install -e . --group dev
```

The development dependency group includes pytest and httpx. The project does not currently declare an ASGI server package in `pyproject.toml`; install/configure one (such as Uvicorn) in the environment before launching the API if it is not already available. For example, after activating `.venv`:

```powershell
python -m pip install uvicorn
python -m uvicorn app.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`. Health and interactive API documentation are available at `/api/health` and `/docs` respectively.

To run the mocked backend tests:

```powershell
python -m pytest -q
```

Tests should use mocked services and must not require live model/API calls or a database connection.

## Frontend setup

In another terminal, from the project root:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite (normally `http://127.0.0.1:5173`). To run the production type-check and build:

```powershell
npm run build
```

To run frontend unit tests:

```powershell
npm test
```

If the frontend needs a different API address, configure `VITE_API_BASE_URL` using `frontend/.env.example` as a reference. This is a browser-visible URL setting; never put credentials or API keys in `VITE_*` variables.

## Live execution and data safety

Keep live execution disabled for ordinary local development. The backend gate is controlled by `ENABLE_LIVE_AGENTS`; the request must also explicitly specify `execution_mode: "live"`. Setting the server variable alone does not make mock requests live. If the gate is disabled, live requests should be rejected; the application must not silently fall back to mock mode.

For a local PowerShell session, explicitly disable the gate with:

```powershell
$env:ENABLE_LIVE_AGENTS = "false"
```

Enabling live execution can call Groq and may execute the selected agent workflow. Only enable it when credentials, network access, data handling, and database permissions have been deliberately configured. Do not commit `.env` files or expose credentials in frontend configuration.

ETL extraction contacts the URL explicitly submitted by the user. Use only trusted endpoints and review downloaded data. Mock transformation does not perform a real transformation or create a dataset.

The SQL agent is intended to use read-only SQL checks and a read-only transaction, but these controls are not a substitute for database-side permissions. Verify a dedicated least-privilege PostgreSQL role before live use. Do not expose the application to multiple users: authentication and per-user isolation are not implemented, and run history and managed datasets are shared by API callers.

### Destructive database loader

`scripts/database/feed_db.py` loads the sample rideshare CSV files from `data/`. It contains `TRUNCATE ... CASCADE` operations and connects to PostgreSQL as part of its execution. It can delete existing data in its target tables. **Do not run it against a database with data you need to keep.** Use only a disposable database after reviewing the script and its configuration. It is intentionally not part of the normal setup steps.

### Local transform example

From the repository root, `python scripts/examples/transform_pokemon.py` reads `data/extract/extracted_data.csv` and writes `data/transformed/transformed_data.csv`. It refuses to overwrite an existing output file. This example does not fetch data itself.

## Generated data and local artifacts

Local input datasets belong under `data/`. The web application stores managed outputs, metadata, and its SQLite run-history database under `app_data/`. These paths and local environments/build outputs are Git-ignored. Do not put credentials, customer data, or sensitive database samples in tracked files.

The tracked `test_schema_details.txt` is a generated schema-inspection artifact and may contain database sample rows. It has not been reviewed as part of the repository cleanup. Treat it as potentially sensitive and inspect/sanitize it before sharing the repository.

## Current verification status

This project is still in development. Some mocked backend checks and frontend builds are documented in `BUILD_PLAN.md`; live LangGraph/Groq execution, external-provider behavior, database permission verification, and complete browser coverage remain unverified. Read the phase status and blockers in `BUILD_PLAN.md` and the security findings in `CLEANUP_AUDIT.md` before relying on the application.
>>>>>>> 6c48632 (security: harden legacy ETL and database workflows)
