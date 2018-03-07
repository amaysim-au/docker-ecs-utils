ifdef GO_PIPELINE_LABEL
	BUILD_VERSION?=$(GO_PIPELINE_LABEL)
else
	BUILD_VERSION?=local
endif

DOCKER_NAMESPACE=634961025262.dkr.ecr.ap-southeast-2.amazonaws.com
DOCKER_IMAGE=nginx:latest

ifdef DOTENV
	DOTENV_TARGET=dotenv
else
	DOTENV_TARGET=.env
endif

.env:
	@echo "Create .env with .env.template"
	cp .env.template .env
	echo "" >> .env
	echo "BUILD_VERSION=$(BUILD_VERSION)" >> .env

# Create/Overwrite .env with $(DOTENV)
dotenv:
	@echo "Overwrite .env with $(DOTENV)"
	cp $(DOTENV) .env
	echo "BUILD_VERSION=$(BUILD_VERSION)" >> .env

deploy: $(DOTENV)
	docker-compose down
	docker-compose run --rm ecs make -f /scripts/Makefile deploy
	docker-compose down

cutover: $(DOTENV)
	docker-compose down
	docker-compose run --rm ecs make -f /scripts/Makefile cutover
	docker-compose down
