deploy:
	export LANG=C.UTF-8
	envsubst < deployment/ecs.json > deployment/ecs-env.json
	envsubst < deployment/ecs-config.yml > deployment/ecs-config-env.yml
	/scripts/deploy.py

cutover:
	export LANG=C.UTF-8
	envsubst < deployment/ecs.json > deployment/ecs-env.json
	envsubst < deployment/ecs-config.yml > deployment/ecs-config-env.yml
	/scripts/cutover.py
