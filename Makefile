ifdef DOTENV
	DOTENV_TARGET=dotenv
else
	DOTENV_TARGET=.env
endif

VERSION = 2.9.1
IMAGE_NAME ?= amaysim/ecs-utils:$(VERSION)
TAG = $(VERSION)

##################
# PUBLIC TARGETS #
##################
dockerBuild:
	docker build -t $(IMAGE_NAME) .

ecrLogin:
	$(shell aws ecr get-login --no-include-email --region ap-southeast-2)

dockerPush: ecrLogin
	docker push $(IMAGE_NAME)

shell: $(DOTENV_TARGET)
	docker-compose down
	docker-compose run --rm shell

lint: $(DOTENV_TARGET)
	docker-compose run --rm flake8 --ignore 'E501' scripts/*.py
	docker-compose run --rm pylint scripts/*.py
	docker-compose run --rm cfn-python-lint cfn-lint -t scripts/ecs-cluster-application-version.yml

test: $(DOTENV_TARGET)
	docker-compose down
	docker-compose run --rm ecs scripts/test.py

gitTag:
	-git tag -d $(TAG)
	-git push origin :refs/tags/$(TAG)
	git tag $(TAG)
	git push origin $(TAG)

clone: $(DOTENV_TARGET)
	docker-compose run --rm --entrypoint=sh cookiecutter -c "cookiecutter --no-input --overwrite-if-exists . project_name='ECS Utils Test Project' ecr_aws_account_id=\$$ECR_AWS_ACCOUNT_ID"
	$(MAKE) -C ecs-utils-test-project .env

example: $(DOTENV_TARGET)
	docker-compose run --rm --entrypoint=sh cookiecutter -c "cookiecutter --no-input --overwrite-if-exists . project_name='Example' ecr_aws_account_id=123456789987"
.PHONY: example

recursive:
	$(MAKE) -C ecs-utils-test-project dockerBuild ecrLogin dockerPush autocleanup deploy cutover

###########
# ENVFILE #
###########
# Create .env based on .env.template if .env does not exist
.env:
	@echo "Create .env with .env.template"
	cp .env.template .env

# Create/Overwrite .env with $(DOTENV)
dotenv:
	@echo "Overwrite .env with $(DOTENV)"
	cp $(DOTENV) .env

$(DOTENV):
	$(info overwriting .env file with $(DOTENV))
	cp $(DOTENV) .env
.PHONY: $(DOTENV)
