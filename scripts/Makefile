deploy:
	export LANG=C.UTF-8
	aws configure set default.region ap-southeast-2
	envsubst < /deployment/ecs.json > /deployment/ecs-env.json
	envsubst < /deployment/ecs-config.yml > /deployment/ecs-config-env.yml
	/scripts/deploy.py $(ECS_APP_NAME) $(ECS_CLUSTER_NAME) $(ECS_DESIRED_TASKS) $(ECS_IAM_ROLE)
