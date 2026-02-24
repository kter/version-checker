# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Version Checker is a full-stack web application that monitors framework versions and End-of-Life (EOL) status across GitHub repositories. The application uses Clean Architecture with Domain-Driven Design.

- **Frontend**: Nuxt 3 (TypeScript) with Nuxt UI
- **Backend**: FastAPI (Python 3.12)
- **Database**: Amazon Aurora DSQL (PostgreSQL-compatible) with IAM authentication
- **Cache**: DynamoDB for EOL status caching
- **Authentication**: GitHub OAuth with JWT tokens

## Development Commands

### Full Stack (Docker)

```bash
make setup           # Full setup: generate .env from Terraform, build, start
make build           # Build Docker containers
make up              # Start services in background
make down            # Stop all services
make logs            # View container logs
make setup-env       # Generate .env from Terraform outputs
```

### Frontend (in `/frontend/`)

```bash
npm install          # Install dependencies
npm run dev          # Start dev server (localhost:3000)
npm run build        # Build for production
npm run preview      # Preview production build
npm run test:unit    # Run unit tests (Vitest)
npm run test:e2e     # Run e2e tests (Playwright)
```

### Backend (in `/backend/`)

```bash
# Uses Poetry for dependency management
poetry install                # Install dependencies
poetry run pytest             # Run all tests
poetry run pytest -v          # Run tests with verbose output
poetry run pytest tests/unit  # Run unit tests only
poetry run pytest tests/integration  # Run integration tests only
poetry run black .            # Format code
```

## Architecture

### Clean Architecture Layers

The backend follows strict layer separation:

- **`domain/`** - Business entities (dataclasses) and repository interfaces
- **`adapters/`** - Infrastructure implementations (SQLAlchemy models, database repo, DynamoDB cache)
- **`usecases/`** - Business logic (repository scanning)
- **`infrastructure/`** - External dependencies (database connection, config)
- **`api/`** - HTTP layer (routes, authentication)

Key pattern: Domain entities have no dependencies; adapters implement domain interfaces.

### Database (Aurora DSQL)

DSQL uses IAM authentication with auto-generated tokens:

1. **Token Generation**: `get_dsql_auth_token()` generates tokens via boto3
2. **Dynamic Refresh**: A SQLAlchemy `do_connect` event listener refreshes tokens on each connection (handles expiration)
3. **Connection Pool**: Uses `pool_pre_ping=True` and `AUTOCOMMIT` isolation level
4. **Important**: DSQL only supports single-table DDL operations - migrations must be table-by-table

### API Authentication Flow

1. User clicks "Login with GitHub" → redirects to `/api/v1/auth/login`
2. GitHub OAuth callback → `/api/v1/auth/callback` returns JWT
3. JWT contains GitHub access token (stored client-side, not persistent)
4. Organization access verified on each API call using GitHub token
5. `Authorization: Bearer <jwt>` required for scan endpoints

### Caching Strategy

- DynamoDB caches EOL status responses
- Cache-first approach: check cache before triggering new scan
- Manual cache refresh via `POST /api/v1/scan/orgs/{org_id}`
- No automatic invalidation

## Key Implementation Details

### Scanner Mock

The repository scanner (`usecases/scanner.py`) is currently mocked with hardcoded data (Nuxt 2.15.8 EOL example). Real implementation should:

1. Fetch repository package.json via GitHub API
2. Parse framework versions (Nuxt, Vue, React, etc.)
3. Check EOL status against official sources
4. Cache results in DynamoDB

### Database Models

Schema (adapters/models.py):
- `User` - GitHub user data
- `Organization` - GitHub organizations
- `Repository` - GitHub repositories
- `EolStatus` - Framework version status (not yet persisted to DB)

### Environment Configuration

- `ENV=local|dev|prd` - Controls AWS profile usage and SQL echo
- `AWS_PROFILE=dev` - Local development AWS profile
- Terraform outputs auto-generated to `.env` via `make setup-env`
- Frontend uses `NUXT_PUBLIC_API_BASE` for backend URL

### CI/CD

- `.github/workflows/ci.yml` - Main branch CI (build, lint, typecheck)
- `.github/workflows/daily-scan.yml` - Daily scan of all organizations (17:00 UTC)
- Terraform manages DSQL and DynamoDB with workspace isolation (dev/prd)

## Deployment

**IMPORTANT: Always use make commands for deployment. Do not directly run terraform or deployment scripts.**

```bash
make deploy-dev    # Deploy full infrastructure to dev environment
make deploy-prd    # Deploy full infrastructure to prd environment
make build-lambda  # Build Lambda deployment package (before deploy-lambda)
make deploy-lambda # Deploy Lambda function only (requires ENV=dev|prd)
make deploy-frontend ENV=dev|prd  # Deploy frontend to S3 + CloudFront
```

Deployment commands:
- `deploy-dev` - Full infrastructure deployment to dev (Terraform + environment setup)
- `deploy-prd` - Full infrastructure deployment to prd (Terraform + environment setup)
- `build-lambda` - Builds the Lambda zip package from backend code
- `deploy-lambda` - Updates only the Lambda function (use `ENV=dev|prd`)
- `deploy-frontend` - Deploys frontend static files to S3 and invalidates CloudFront (use `ENV=dev|prd`)

### Testing

**Frontend tests**: Vitest for unit tests, Playwright for e2e tests
**Backend tests**: pytest with pytest-asyncio; fixtures in `tests/conftest.py`
**CI tests**: Use mocks for dependencies (no real AWS/database access in CI)
