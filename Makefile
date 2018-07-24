ifdef DOTENV
	DOTENV_TARGET=dotenv
else
	DOTENV_TARGET=.env
endif

VERSION = 2.7.0-alb-scaling-v2
IMAGE_NAME ?= amaysim/ecs-utils:$(VERSION)
TAG = $(VERSION)

dockerBuild:
	docker build -t $(IMAGE_NAME) .

ecrLogin:
	$(shell aws ecr get-login --no-include-email --region ap-southeast-2)

dockerPush: ecrLogin
	docker push $(IMAGE_NAME)

shell:
	docker-compose down
	docker-compose run --rm shell

lint:
	docker-compose run --rm flake8 --ignore 'E501' scripts/*.py
	docker-compose run --rm pylint scripts/*.py

test:
	docker-compose down
	docker-compose run --rm ecs scripts/test.py

gitTag:
	-git tag -d $(TAG)
	-git push origin :refs/tags/$(TAG)
	git tag $(TAG)
	git push origin $(TAG)
