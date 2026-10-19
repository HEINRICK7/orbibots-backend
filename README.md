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
.\venv\Scripts\python.exe -m uvicorn app.src.main:app --reload
```

Or run via `run.py`:

```powershell
.\venv\Scripts\python.exe run.py
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

`COMPANY_ADMIN` is a company-scoped membership role. Global platform access is
separate: only users with global `ADMIN` may use routes protected by the
platform-administration dependency. A global role does not create or bypass
company memberships.

The migration adds nullable `users.global_role`, constrained to `ADMIN` or
`NULL`. Set `INITIAL_COMPANY_NAME`, both initial-admin names and emails,
`GLOBAL_ADMIN_ALLOWED_EMAILS` to those exact two email identities (comma
separated), and two distinct passwords in the ignored local `.env` file. The
allowlist is trusted application configuration, not a user-editable database
setting. Downgrading the global-role migration removes all role assignments;
confirm the impact before rolling it back. Each password must contain at least
20 characters. Generate a separate random password for each user:

```powershell
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep passwords out of chat, Git, migration files, and command-line arguments.
Run the explicit provisioning command after PostgreSQL is running and the
Alembic migrations have been applied:

```powershell
.\venv\Scripts\python.exe -m app.src.bootstrap.initial_admins
```

The command creates the company as `ACTIVE`, creates missing users with
Argon2 password hashes, assigns active `COMPANY_ADMIN` memberships, and grants
global `ADMIN` only to the two allowlisted identities. The allowlist must
contain exactly two distinct valid email addresses and match the initial
account identities; otherwise provisioning fails before database changes.
Provisioning is safe to rerun: existing accounts are not given new passwords,
and conflicting inactive accounts or memberships cause an explicit error.

## Project layout

```text
app/src/
├── domain/
│   ├── authentication/
│   └── company_onboarding/
├── application/
│   └── authentication/
│       ├── use_cases/
│       └── ports/
├── infrastructure/
│   ├── authentication/
│   ├── company_onboarding/
│   ├── config/
│   └── persistence/
├── presentation/
│   └── api/
│       ├── authentication/
│       └── health_check/
├── bootstrap/
└── main.py

tests/
├── unit/
│   ├── domain/
│   └── application/
└── integration/
    ├── infrastructure/
    └── api/
```

Dependencies point inward: domain and application code do not import FastAPI,
SQLAlchemy, Punq, or cryptographic libraries. Infrastructure implements
application ports declared as `Protocol`s. Presentation translates HTTP and
depends on use cases; `app/src/bootstrap/` wires those use cases to concrete
adapters, and `app/src/main.py` exposes `app = create_app()`.

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
