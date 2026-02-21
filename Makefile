.PHONY: setup setup-env deploy-dev deploy-prd down logs build

setup: setup-env build up

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

setup-env:
	chmod +x ./scripts/generate_local_env.sh
	./scripts/generate_local_env.sh

deploy-dev:
	cd terraform && terraform init && \
	terraform workspace select dev || terraform workspace new dev && \
	terraform apply -var="env=dev" -auto-approve
	@echo "Deploy dev complete. Generating local .env..."
	make setup-env

deploy-prd:
	cd terraform && terraform init && \
	terraform workspace select prd || terraform workspace new prd && \
	terraform apply -var="env=prd" -auto-approve
