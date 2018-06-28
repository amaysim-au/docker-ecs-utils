VERSION = 2.5.9
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

gitTag:
	-git tag -d $(TAG)
	-git push origin :refs/tags/$(TAG)
	git tag $(TAG)
	git push origin $(TAG)

# Example of how to deploy using docker compose
deploy:
	docker-compose down
	docker-compose run --rm rancher make -f /scripts/Makefile deploy
