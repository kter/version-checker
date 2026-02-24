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
