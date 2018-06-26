ifndef ECS_TASK_DEFINITION
	ECS_TASK_DEFINITION=deployment/ecs.json
endif
ifndef ECS_CONFIG
	ECS_CONFIG=deployment/ecs-config.yml
endif

deploy:
	export LANG=C.UTF-8
	envsubst < $(ECS_TASK_DEFINITION) > deployment/ecs-env.json
	envsubst < $(ECS_CONFIG) > deployment/ecs-config-env.yml
	/scripts/deploy.py

cutover:
	export LANG=C.UTF-8
	envsubst < $(ECS_TASK_DEFINITION) > deployment/ecs-env.json
	envsubst < $(ECS_CONFIG) > deployment/ecs-config-env.yml
	/scripts/cutover.py

cleanup:
	export LANG=C.UTF-8
	/scripts/cleanup.py

autocleanup:
	export LANG=C.UTF-8
	/scripts/autocleanup.py
