ifdef GO_PIPELINE_LABEL
	BUILD_VERSION?=$(GO_PIPELINE_LABEL)
else
	BUILD_VERSION?=local
endif
ifdef AWS_ROLE
	ASSUME_REQUIRED?=assumeRole
endif
ifdef DOTENV
	DOTENV_TARGET=dotenv
else
	DOTENV_TARGET=.env
endif

# Just an example, not building the image here
DOCKER_NAMESPACE=quay.io
DOCKER_IMAGE=$(DOCKER_NAMESPACE)/assemblyline/ok:$(BUILD_VERSION)

deploy: $(DOTENV_TARGET) $(ASSUME_REQUIRED)
	docker-compose down
	docker-compose run --rm ecs make -f /scripts/Makefile deploy
	docker-compose down

cutover: $(DOTENV_TARGET) $(ASSUME_REQUIRED)
	docker-compose down
	docker-compose run --rm ecs make -f /scripts/Makefile cutover
	docker-compose down

cleanup: $(DOTENV_TARGET) $(ASSUME_REQUIRED)
	docker-compose down
	docker-compose run --rm ecs make -f /scripts/Makefile cleanup
	docker-compose down

assumeRole: $(DOTENV_TARGET)
	docker run --rm -e "AWS_ACCOUNT_ID" -e "AWS_ROLE" amaysim/aws:1.1.3 assume-role.sh >> $(DOTENV_TARGET)
.PHONY: assumeRole

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
