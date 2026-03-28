# AGENTS.md

## Scope

Instructions for the entire repository.

More specific instructions may exist in nested `AGENTS.md` files. When instructions conflict, the nearer file takes precedence.

## Overview

This repository is a full-stack version monitoring app built on a split frontend/backend/infrastructure layout.

- `frontend/`: Nuxt application with i18n, Vitest, and Playwright
- `backend/`: FastAPI application managed with Poetry
- `terraform/`: AWS infrastructure definitions

## Shared Rules

- The root `Makefile` is the canonical entry point for project commands.
- Use the tool versions defined in `mise.toml`.
- Implement i18n for all user-facing text.
- Add or update tests for every new feature and bug fix.
- Add reusable workflow shortcuts to the root `Makefile`.
- Run cross-stack workflows, deployment, and Terraform operations from the repository root.
- Use root `make` targets for project workflows. Do not run direct `terraform apply`, `docker build`, or deployment scripts when an equivalent `make` target exists.

## Common Commands

```bash
make setup
make test
make install-hooks
make switch-env ENV=dev
make deploy-dev
make deploy-prd
```
