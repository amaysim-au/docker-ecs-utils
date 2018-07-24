ifdef GO_PIPELINE_LABEL
	BUILD_VERSION?=$(GO_PIPELINE_LABEL)
	ENV_RM_REQUIRED?=rm_env
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

DOCKER_NAMESPACE={{ cookiecutter.ecr_aws_account_id }}.dkr.ecr.ap-southeast-2.amazonaws.com/{{ cookiecutter.docker_namespace }}
DOCKER_IMAGE=$(DOCKER_NAMESPACE)/{{ cookiecutter.docker_image }}

##################
# PUBLIC TARGETS #
##################

deploy: $(ENV_RM_REQUIRED) $(DOTENV_TARGET) $(ASSUME_REQUIRED)
	docker-compose down
	docker-compose run --rm ecs make -f /scripts/Makefile deploy
	docker-compose down

cutover: $(ENV_RM_REQUIRED) $(DOTENV_TARGET) $(ASSUME_REQUIRED)
	docker-compose down
	docker-compose run --rm ecs make -f /scripts/Makefile cutover
	docker-compose down

cleanup: $(ENV_RM_REQUIRED) $(DOTENV_TARGET) $(ASSUME_REQUIRED)
	docker-compose down
	docker-compose run --rm ecs make -f /scripts/Makefile cleanup
	docker-compose down

autocleanup: $(ENV_RM_REQUIRED) $(DOTENV_TARGET) $(ASSUME_REQUIRED)
	docker-compose down
	docker-compose run --rm ecs make -f /scripts/Makefile autocleanup
	docker-compose down

assumeRole: $(DOTENV_TARGET)
	docker run --rm -e "AWS_ACCOUNT_ID" -e "AWS_ROLE" amaysim/aws:1.1.3 assume-role.sh >> $(DOTENV_TARGET)
.PHONY: assumeRole

dockerBuild:
	docker build -t $(DOCKER_IMAGE):$(BUILD_VERSION) .
	docker tag $(DOCKER_IMAGE):$(BUILD_VERSION) $(DOCKER_IMAGE):latest

ecrLogin: $(ENV_RM_REQUIRED) $(DOTENV_TARGET)
	$(shell aws ecr get-login --no-include-email --region ap-southeast-2)

dockerPush:
	docker push $(DOCKER_IMAGE):$(BUILD_VERSION)
	docker push $(DOCKER_IMAGE):latest

###########
# ENVFILE #
###########

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

# Removes the .env file before each deploy to force regeneration without cleaning the whole environment
rm_env:
	rm -f .env

###################
# PRIVATE TARGETS #
###################

