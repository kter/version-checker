.PHONY: setup build up down logs switch-env setup-local setup-dev setup-prd deploy-dev deploy-prd build-lambda deploy-lambda deploy-frontend

setup: build up

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

# Switch to different environment (local/dev/prd)
switch-env:
	@if [ -z "$(ENV)" ]; then \
		echo "Error: Please specify ENV=local|dev|prd"; \
		exit 1; \
	fi
	chmod +x ./scripts/switch_env.sh
	./scripts/switch_env.sh $(ENV)

# Setup local environment
setup-local:
	chmod +x ./scripts/generate_env.sh ./scripts/switch_env.sh
	./scripts/generate_env.sh local
	./scripts/switch_env.sh local

# Setup dev environment
setup-dev:
	chmod +x ./scripts/generate_env.sh ./scripts/switch_env.sh
	./scripts/generate_env.sh dev
	./scripts/switch_env.sh dev

# Setup prd environment
setup-prd:
	chmod +x ./scripts/generate_env.sh ./scripts/switch_env.sh
	./scripts/generate_env.sh prd
	./scripts/switch_env.sh prd

# Build Lambda deployment package
build-lambda:
	@echo "Building Lambda deployment package..."
	cd backend && \
	zip -r ../terraform/backend_lambda.zip . \
		-x \*.pyc \*.pyo \*.pyd \
		-x __pycache__/\* \
		-x .pytest_cache/\* \
		-x .venv/\* venv/\* env/\* \
		-x .coverage \*htmlcov \*.pytest_cache \
		-x node_modules/\* \
		-x .git/\* \
		-x \*.zip
	@echo "Lambda package built: terraform/backend_lambda.zip"

# Deploy Lambda function only
deploy-lambda:
	@echo "Deploying Lambda function..."
	@if [ -z "$(ENV)" ]; then \
		echo "Error: Please specify ENV=dev|prd"; \
		exit 1; \
	fi
	cd terraform && terraform workspace select $(ENV) || terraform workspace new $(ENV)
	cd terraform && terraform apply -var="env=$(ENV)" -target=aws_lambda_function.backend -auto-approve
	@echo "Lambda deployed."

# Deploy to AWS dev environment (full infrastructure)
deploy-dev:
	cd terraform && terraform init && \
	terraform workspace select dev || terraform workspace new dev && \
	terraform apply -var="env=dev" -auto-approve
	@echo "Deploy dev complete. Generating .env.dev..."
	make setup-dev

# Deploy to AWS prd environment (full infrastructure)
deploy-prd:
	cd terraform && terraform init && \
	terraform workspace select prd || terraform workspace new prd && \
	terraform apply -var="env=prd" -auto-approve
	@echo "Deploy prd complete. Generating .env.prd..."
	make setup-prd

# Deploy frontend to S3 + CloudFront
deploy-frontend:
	@if [ -z "$(ENV)" ]; then \
		echo "Error: Please specify ENV=dev|prd"; \
		exit 1; \
	fi
	chmod +x ./scripts/deploy_frontend.sh
	./scripts/deploy_frontend.sh $(ENV)

BACKEND_PATH ?= .
FRONTEND_PATH ?= .
TERRAFORM_PATH ?= .

.PHONY: test
test: test-unit test-lint

.PHONY: test-unit
test-unit: test-unit-backend test-unit-frontend

.PHONY: test-unit-backend
test-unit-backend:
	cd backend && poetry run pytest tests/unit

.PHONY: test-unit-frontend
test-unit-frontend:
	cd frontend && npm run test:unit

.PHONY: test-integration
test-integration:
	cd backend && poetry run pytest tests/integration

.PHONY: stop-hook-unit-tests
stop-hook-unit-tests: test-unit

.PHONY: lint-backend
lint-backend:
	@target="$(BACKEND_PATH)"; \
	if [ "$$target" = "." ]; then \
		set -- app tests lambda_handler.py; \
	else \
		set -- "$$target"; \
	fi; \
	cd backend && poetry run python -m compileall "$$@"

.PHONY: lint-frontend
lint-frontend:
	cd frontend && npx nuxi typecheck

.PHONY: test-lint
test-lint: lint-backend lint-frontend

.PHONY: format
format: format-backend format-frontend format-terraform

.PHONY: format-check
format-check: format-check-backend format-check-frontend format-check-terraform

.PHONY: format-backend
format-backend:
	cd backend && poetry run black $(BACKEND_PATH)

.PHONY: format-check-backend
format-check-backend:
	cd backend && poetry run black --check $(BACKEND_PATH)

.PHONY: format-frontend
format-frontend:
	@echo "No frontend formatter configured; skipping."

.PHONY: format-check-frontend
format-check-frontend:
	@echo "No frontend formatter configured; skipping."

.PHONY: format-terraform
format-terraform:
	cd terraform && terraform fmt $(TERRAFORM_PATH)

.PHONY: format-check-terraform
format-check-terraform:
	cd terraform && terraform fmt -check $(TERRAFORM_PATH)

.PHONY: claude-post-tool-use
claude-post-tool-use:
	@if [ -z "$(FILE_PATH)" ]; then \
		echo "FILE_PATH is required"; \
		exit 1; \
	fi
	@file_path="$(FILE_PATH)"; \
	case "$$file_path" in \
		backend/*.py) \
			rel_path="$${file_path#backend/}"; \
			$(MAKE) --no-print-directory format-backend BACKEND_PATH="$$rel_path" && \
			$(MAKE) --no-print-directory lint-backend BACKEND_PATH="$$rel_path" ;; \
		frontend/*.js|frontend/*.jsx|frontend/*.ts|frontend/*.tsx|frontend/*.vue) \
			$(MAKE) --no-print-directory lint-frontend ;; \
		terraform/*.tf|terraform/*.tfvars) \
			rel_path="$${file_path#terraform/}"; \
			$(MAKE) --no-print-directory format-terraform TERRAFORM_PATH="$$rel_path" ;; \
		*) \
			true ;; \
	esac

.PHONY: claude-pre-tool-use
claude-pre-tool-use:
	@python3 scripts/claude_pre_tool_use_guard.py

.PHONY: install-hooks
install-hooks:
	mise exec -- lefthook install
	@echo "Git hooks installed via lefthook."
