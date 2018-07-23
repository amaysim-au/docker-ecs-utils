# ECS Utils

A collection of scripts for deploying [AWS ECS Services](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html).

## Features

  * Fully automated deployments
  * Blue/green (or even rainbow) deployments
  * Uses AWS Application Load Balancer routing rules for blue/green, not DNS
  * Uses [3 Musketeers](https://3musketeers.io/)

## Targets

### Deploy

Running `make deploy` deploys a _**version**_ of your application to ECS. The script can derive the version from your CI tool (e.g. `GO_PIPELINE_LABEL`) or you can statically set it for in-place deployments.

The [script](scripts/deploy.py) does the following:

  * The script queries the application's ALB to determine the next available [priority/order](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/listener-update-rules.html)
  * Parses [.env](.env.template) to generate a list of environment variable keys, and then grabs the values from the running environment (i.e. `os.environ.get('MY_VAR')`).
  * The script generates the task definition from the file at [deployment/ecs.json](examples/deployment/ecs.json) as well as the environment variables gathered in the previous step and uploads it to ECS.
  * Create a CloudFormation stack using the template at [scripts/ecs-cluster-application-version.yml](scripts/ecs-cluster-application-version.yml).
  * The script will then poll until this stack is succesfully created. Succesful creation involves the ECS succesfully starting the containers and registering them to the target group.
  * The script polls the Target Group to ensure that all healthchecks are passing.
  * A URL for this specific version is output.

### Cutover

Once you are ready for the version you've deployed to start receiving _live_ traffic, you can do a cutover by running `make cutover`.

This involves changing the ALB's default rule to point to the version you deployed. Changing ALB rules is atomic and instantly takes effect.

After cutting over, the old versions still exist. This is so you can instantly cut back by running the cutover stage in the old pipeline.

### Auto Cleanup

At some point you will want to clean up old deployments. Running `make autocleanup` will remove _any versions that are not live_ by deleting the CloudFormation stacks.

## Example

See the [example](example/) for more detail on how to use it. You can copy these files to your app and use them after updating:

  * `DOCKER_NAMESPACE`/`DOCKER_IMAGE` in the [Makefile](example/Makefile) (i.e. `<YOUR AWS ACCOUNT ID HERE>` and the namespace/image name).
  * `image` in [deployment/ecs.json](examples/deployment/ecs.json)
