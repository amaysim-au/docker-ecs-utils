# ECS Utils

A collection of scripts for deploying [AWS ECS Services](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html).

## Features

  * Fully automated deployments
  * Blue/green (or even rainbow) deployments
  * Uses AWS Application Load Balancers for blue/green, not DNS
  * Uses [3 Musketeers](https://3musketeers.io/)

## Targets

### Deploy

Running `make deploy` deploys a _**version**_ of your application to ECS. 

The [script](scripts/deploy.py) does the following:

  * Query the application's ALB to determine the [priority/order](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/listener-update-rules.html) of the rule that it is creating
  * Parses `.env` to generate a list of environment variable keys, and then grabs the values from the running environment (i.e. `os.environ.get('MY_VAR')`).
  * Uploads a task definition to ECS. The task definition is generated from the file at [deployment/ecs.json](examples/deployment/ecs.json) as well as the environment variables gathered in the previous step.
  * Create a CloudFormation stack using the template at [scripts/ecs-cluster-application-version.yml](scripts/ecs-cluster-application-version.yml). Parameters are gathered from [environment variables](.env.template) and a static file located at [deployment/ecs-config.yml](examples/deployment/ecs-config.yml).
  * The script will then poll until this stack is succesfully created. Succesful creation involves the containers being created and registered to the Target Group.
  * The Target Group is polled to ensure that all healthchecks are passing.
  * A URL for this specific version is output.

### Cutover

Once you are ready for the version you've deployed to start receiving _live_ traffic, you can do a cutover by running `make cutover`.

This involves changing the ALB's default rule to point to the version you deployed. Changing ALB rules is atomic and instantly takes effect.

### Auto Cleanup

After cutting over, the old versions still exist. This is so you can instantly cut back should you run in to any issues.

However, at some point you will want to clean up old deployments. Running `make autocleanup` will remove _any versions that are not live_ by deleting the CloudFormation stacks.
