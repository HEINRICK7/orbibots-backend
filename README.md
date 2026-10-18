# OrbiBots backend

## Database setup

The initial persistence layer uses PostgreSQL, SQLAlchemy models, and Alembic
migrations. `Company` is the tenant boundary; `MembershipScope` is a PostgreSQL
enum with the V1 values `COMPANY` and `ASSIGNED_AGENTS`.

Install the Python dependencies:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your PostgreSQL host, database, username, password, and
`DATABASE_URL`, then configure `APP_ENV` and `JWT_SECRET_KEY`. `.env` is ignored
by Git. Keep real credentials out of `.env.example` and encode special
characters in the URL password. The example signing key is for local
development only. For production, set a random key of at least 32 characters,
for example by running
`.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Run the API

In PowerShell, from the project root, install dependencies and create the local
environment file if it does not exist:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` if needed. Start PostgreSQL and apply database migrations:

```powershell
docker compose up -d --wait postgres
.\venv\Scripts\alembic.exe upgrade head
```

Start the development server:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The server is available at `http://127.0.0.1:8000`; interactive API
documentation is at `http://127.0.0.1:8000/docs`. Stop the development server
with Ctrl+C. Login is available at `POST /auth/login` with an email and
password; successful login returns a signed JWT bearer access token.
`GET /auth/me` demonstrates bearer token authentication. Production startup
requires `DATABASE_URL` and a `JWT_SECRET_KEY` of at least 32 characters. The
signing algorithm is HS256 and `ACCESS_TOKEN_EXPIRE_MINUTES` accepts values
from 1 to 1440.

This change does not provide account enrollment or password setup. Existing
users have a nullable password hash and cannot log in until a separate secure
provisioning flow sets one; no default password is created.

## Initial company administrators

The existing schema already supports `COMPANY_ADMIN` memberships. Alembic does
not need a schema migration to create the initial company and its users.

Set `INITIAL_COMPANY_NAME`, both admin names and emails, and two distinct
passwords in the ignored local `.env` file. Each password must contain at least
20 characters. Generate a separate random password for each user:

```powershell
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep passwords out of chat, Git, migration files, and command-line arguments.
Run the explicit provisioning command after PostgreSQL is running and the
Alembic migrations have been applied:

```powershell
.\venv\Scripts\python.exe -m app.bootstrap.initial_admins
```

The command creates the company as `ACTIVE`, creates missing users with
Argon2 password hashes, and assigns active `COMPANY_ADMIN` memberships. It is
safe to rerun: existing accounts are not given new passwords, and conflicting
inactive accounts or memberships cause an explicit error.

## Project layout

```text
app/
  bootstrap/
  contexts/
    authentication/
      application/
        use_cases/
      domain/
      infrastructure/
      presentation/
    company_onboarding/
      application/
      domain/
      infrastructure/
  platform/
migrations/
tests/
```

- `app/main.py` exposes the ASGI object as `app.main:app`.
- `app/contexts/` holds business capabilities, grouped by bounded context.
- `app/contexts/authentication/domain/` holds framework-independent identity
  types and authentication errors.
- `app/contexts/authentication/application/` holds ports and application
  contracts.
- `app/contexts/authentication/application/use_cases/` holds one class per
  authentication action: `LoginUseCase` and `AuthenticateUserUseCase`.
- `app/contexts/authentication/infrastructure/` adapts SQLAlchemy, password
  hashing, and JWT libraries to application ports.
- `app/contexts/authentication/presentation/` holds FastAPI routes,
  request/response schemas, and HTTP dependency adapters. It does not construct
  concrete infrastructure adapters.
- `app/contexts/company_onboarding/domain/` holds onboarding domain concepts,
  such as `MembershipScope`.
- `app/contexts/company_onboarding/application/` is reserved for onboarding
  use cases and ports when those behaviors are implemented.
- `app/contexts/company_onboarding/infrastructure/` holds SQLAlchemy mappings
  for companies, memberships, invitations, and audit events.
- `app/platform/` holds cross-cutting settings and SQLAlchemy base setup.
- `app/bootstrap/` creates the FastAPI application and Punq container, wires
  infrastructure adapters into use cases, and imports all ORM models for
  Alembic metadata. Authentication wiring lives in
  `app/bootstrap/authentication.py`; initial company-admin provisioning lives
  in `app/bootstrap/initial_admins.py`.
- `migrations/` contains Alembic environment configuration and versioned schema
  changes. Moving Python modules must not create a migration by itself.
- `tests/` contains unit, HTTP integration, architecture-boundary, and
  PostgreSQL schema tests.
- `openspec/` holds capability specifications and change proposals.
- `.agents/` and `.github/` hold repository-specific agent skills and
  configuration; they are not runtime application code.

Dependencies point inward: domain and application code do not import FastAPI,
SQLAlchemy, Punq, or cryptographic libraries. Infrastructure implements
application ports declared as `Protocol`s. Presentation translates HTTP and
depends on use cases; bootstrap wires those use cases to concrete adapters.
Application tests inject in-memory fakes through the same ports without
requiring FastAPI or a database.

Start the isolated PostgreSQL test database and wait for its health check:

```powershell
docker compose up -d --wait postgres
```

Compose, Alembic, and the integration tests load connection settings from
`.env`. Run migrations and the full suite:

```powershell
.\venv\Scripts\alembic.exe upgrade head
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

The authentication application, presentation, HTTP, and architecture tests can
run without PostgreSQL:

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_authentication_application tests.test_authentication_presentation tests.test_authentication tests.test_architecture_boundaries -v
```

The PostgreSQL schema tests remain integration tests. If the test database is
unavailable, the suite reports them as skipped with the required startup
command; it does not replace schema checks with mocks.

Stop the database while preserving its test data:

```powershell
docker compose down
```

To remove the disposable test database and its volume as well:

```powershell
docker compose down --volumes
```

Do not use test credentials or a test database for production.
