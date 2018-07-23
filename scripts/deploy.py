#!/usr/bin/env python3
"""Command-line utility to deploy an AWS ECS Service as well as some helper functions"""

import os
import re
import datetime
import json
import yaml
import boto3
import botocore


def get_priority(rules):
    """Returns the next available priority when given the response from aws elbv2 describe-rules"""

    priorities = [rule['Priority'] for rule in rules]
    i = 1
    rule_priority = None
    while not rule_priority:  # increment from 1 onwards until we find a priority that is unused
        if not str(i) in priorities:
            return i
        else:
            i = i + 1


def create_or_update_stack(stack_name, template, parameters, tags):
    """Update or create stack synchronously, returns the stack ID"""

    cloudformation = boto3.client('cloudformation')

    template_data = _parse_template(template)

    params = {
        'StackName': stack_name,
        'TemplateBody': template_data,
        'Parameters': parameters,
        'Tags': tags
    }

    try:
        if _stack_exists(stack_name):
            print('Updating {}'.format(stack_name))
            stack_result = cloudformation.update_stack(**params)
            waiter = cloudformation.get_waiter('stack_update_complete')
        else:
            print('Creating {}'.format(stack_name))
            stack_result = cloudformation.create_stack(**params)
            waiter = cloudformation.get_waiter('stack_create_complete')
        print("...waiting for stack to be ready...")
        waiter.wait(StackName=stack_name)
    except botocore.exceptions.ClientError as ex:
        error_message = ex.response['Error']['Message']
        if error_message == 'No updates are to be performed.':
            print("No changes")
        else:
            raise
    else:
        return cloudformation.describe_stacks(StackName=stack_result['StackId'])


def _parse_template(template):
    cloudformation = boto3.client('cloudformation')
    cloudformation.validate_template(TemplateBody=template)
    return template


def _stack_exists(stack_name):
    cloudformation = boto3.client('cloudformation')
    try:
        response = cloudformation.describe_stacks(
            StackName=stack_name
        )
        stacks = response['Stacks']
    except (KeyError, botocore.exceptions.ClientError):
        return False
    for stack in stacks:
        if stack['StackStatus'] == 'DELETE_COMPLETE':
            continue
        if stack_name == stack['StackName']:
            return True

    return False


def generate_environment_object():
    """Given a .env file, returns an environment object as per https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html#cloudformationn-ecs-taskdefinition-containerdefinition-environment

    Values are pulled from the running environment."""

    whitelisted_vars = [
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECURITY_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_REGION"
    ]
    environment = []

    env_file = open(os.environ.get('DOTENV', '.env'), 'r').read()

    for env in env_file.split('\n'):
        env = env.split('=')[0]
        if env not in whitelisted_vars and env != '' and not re.match(r'^\s?#', env) and os.environ.get(env, None) is not None:
            environment.append(
                {
                    "name": env,
                    "value": os.environ[env]
                }
            )
    return environment


def get_list_of_rules(app_stack_name):
    """Given a CloudFormation stack name, returns a list of routing rules present on the stack's ALB"""

    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stack_resources(
        StackName=app_stack_name,
        LogicalResourceId='ALBListenerSSL'
    )
    alb_listener = response['StackResources'][0]['PhysicalResourceId']

    client = boto3.client('elbv2')
    response = client.describe_rules(ListenerArn=alb_listener)
    return response['Rules']


def get_load_balancer_type(app_stack_name):
    """Given an application stack, queries CloudFormation and returns the type of load balancer it was created with"""

    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stacks(
        StackName=app_stack_name
    )
    try:
        load_balancer_type = [parameter['ParameterValue'] for parameter in response['Stacks'][0]['Parameters'] if parameter['ParameterKey'] == "LBType"][0]
    except (KeyError, IndexError):
        print('Could not find LBType parameter in response: {}'.format(response))
    return load_balancer_type


def deploy_ecs_service(app_name, env, realm, cluster_name, version, aws_hosted_zone, base_path, config, task_definition, template):
    """Core function for deploying an ECS Service"""

    print("Beginning deployment of {}...".format(app_name))

    version_stack_name = "ECS-{cluster_name}-App-{app_name}-{version}".format(
        cluster_name=cluster_name,
        app_name=app_name,
        version=version
    )
    app_stack_name = "ECS-{cluster}-App-{app}".format(cluster=cluster_name, app=app_name)

    load_balancer_type = get_load_balancer_type(app_stack_name)
    print("Load balancer type is {}.".format(load_balancer_type))

    print("Loading configuration files...")

    print("Generating environment variable configuration...")
    environment = generate_environment_object()
    for index, value in enumerate(task_definition['containerDefinitions']):  # pylint: disable=unused-variable
        task_definition['containerDefinitions'][index]['environment'] = environment
    print("Task definition generated:")
    print(json.dumps(task_definition, indent=2, default=str))

    print("Generating Parmeters for CloudFormation template")
    if load_balancer_type != "None":  # this is intentionally a string
        container_port = [x['portMappings'][0]['containerPort'] for x in task_definition['containerDefinitions'] if x['name'] == app_name][0]

    parameters = [
        {
            "ParameterKey": "Name",
            "ParameterValue": app_name
        },
        {
            "ParameterKey": 'ClusterName',
            "ParameterValue": cluster_name
        },
        {
            "ParameterKey": 'Environment',
            "ParameterValue": env
        },
        {
            "ParameterKey": 'Version',
            "ParameterValue": version
        },
        {
            "ParameterKey": 'LBType',
            "ParameterValue": load_balancer_type
        }
    ]

    if load_balancer_type != "None":  # this is intentionally a string
        extra_parameters = [
            {
                "ParameterKey": 'HealthCheckPath',
                "ParameterValue": config['lb_health_check']
            },
            {
                "ParameterKey": 'HealthCheckGracePeriod',
                "ParameterValue": str(config['lb_health_check_grace_period'])
            },
            {
                "ParameterKey": 'ContainerPort',
                "ParameterValue": str(container_port)
            },
            {
                "ParameterKey": 'Domain',
                "ParameterValue": aws_hosted_zone
            },
            {
                "ParameterKey": 'Path',
                "ParameterValue": base_path
            }
        ]
        for extra_parameter in extra_parameters:
            parameters.append(extra_parameter)
    else:
        extra_parameters = [
            {
                "ParameterKey": 'HealthCheckPath',
                "ParameterValue": ""
            },
            {
                "ParameterKey": 'ContainerPort',
                "ParameterValue": ""
            },
            {
                "ParameterKey": 'Domain',
                "ParameterValue": ""
            },
            {
                "ParameterKey": 'Path',
                "ParameterValue": ""
            },
            {
                "ParameterKey": 'RulePriority',
                "ParameterValue": "-1"
            },
            {
                "ParameterKey": 'AlbScheme',
                "ParameterValue": ""
            }
        ]
        for extra_parameter in extra_parameters:
            parameters.append(extra_parameter)

    print("Uploading Task Definition...")
    ecs = boto3.client('ecs')
    response = ecs.register_task_definition(**task_definition)
    task_definition_arn = response['taskDefinition']['taskDefinitionArn']
    print("Task Definition ARN: {}".format(task_definition_arn))

    cloudformation = boto3.client('cloudformation')
    if load_balancer_type != "None":
        print("Determining ALB Rule priority...")
        priority = None
        listener_rule = None
        try:
            response = cloudformation.describe_stack_resources(
                StackName=version_stack_name,
                LogicalResourceId='ListenerRule'
            )
            listener_rule = response['StackResources'][0]['PhysicalResourceId']
            print("Listener Rule already exists, not setting priority.")
        except (KeyError, IndexError, botocore.exceptions.ClientError):
            print("Listener Rule does not already exist, getting priority...")
        if listener_rule is None:
            rules = get_list_of_rules(app_stack_name)
            priority = get_priority(rules)
        print("Rule priority is {}.".format(priority))

        print("Determining if ALB is internal or internet-facing...")
        elbv2 = boto3.client('elbv2')
        response = cloudformation.describe_stack_resources(
            StackName=app_stack_name,
            LogicalResourceId='ALB'
        )
        alb = response['StackResources'][0]['PhysicalResourceId']
        response = elbv2.describe_load_balancers(
            LoadBalancerArns=[alb],
        )
        alb_scheme = response['LoadBalancers'][0]['Scheme']
        print("ALB is {}.".format(alb_scheme))

    print("Appending additional parameters...")
    parameters.append(
        {
            "ParameterKey": 'TaskDefinitionArn',
            "ParameterValue": task_definition_arn
        }
    )
    if load_balancer_type != "None":
        parameters.append(
            {
                "ParameterKey": 'AlbScheme',
                "ParameterValue": alb_scheme
            }
        )
        if priority is not None:
            parameters.append({
                "ParameterKey": 'RulePriority',
                "ParameterValue": str(priority)
            })
        else:
            parameters.append({
                "ParameterKey": 'RulePriority',
                "UsePreviousValue": True
            })

    if config.get('autoscaling') is not None:
        parameters.append({
            "ParameterKey": 'Autoscaling',
            "ParameterValue": str(config['autoscaling'])
        })
    if config.get('autoscaling_target') is not None:
        parameters.append({
            "ParameterKey": 'AutoscalingTargetValue',
            "ParameterValue": str(config['autoscaling_target'])
        })
    if config.get('autoscaling_max_size') is not None:
        parameters.append({
            "ParameterKey": 'AutoscalingMaxSize',
            "ParameterValue": str(config['autoscaling_max_size'])
        })
    if config.get('autoscaling_min_size') is not None:
        parameters.append({
            "ParameterKey": 'AutoscalingMinSize',
            "ParameterValue": str(config['autoscaling_min_size'])
        })

    print("Finished generating parameters:")
    for param in parameters:
        print("{:30}{}".format(param['ParameterKey'] + ':', param.get('ParameterValue', None)))

    tags = [
        {
            'Key': 'Platform',
            'Value': app_name
        },
        {
            'Key': 'Environment',
            'Value': env
        },
        {
            'Key': 'Realm',
            'Value': realm
        },
        {
            'Key': 'Version',
            'Value': version
        }
    ]

    print("Deploying CloudFormation stack: {}".format(version_stack_name))
    start_time = datetime.datetime.now()
    response = create_or_update_stack(version_stack_name, template, parameters, tags)
    elapsed_time = datetime.datetime.now() - start_time
    print("CloudFormation stack deploy completed in {}.".format(elapsed_time))

    response = cloudformation.describe_stacks(
        StackName=version_stack_name
    )
    outputs = response['Stacks'][0]['Outputs']
    print("CloudFormation stack outputs:")
    for output in outputs:
        print("{:30}{}".format(output['OutputKey'] + ':', output.get('OutputValue', None)))

    if load_balancer_type != "None":
        print("Polling Target Group ({}) until a successful state is reached...".format(version_stack_name))
        elbv2 = boto3.client('elbv2')
        waiter = elbv2.get_waiter('target_in_service')
        response = cloudformation.describe_stack_resources(
            StackName=version_stack_name,
            LogicalResourceId='ALBTargetGroup'
        )
        target_group = response['StackResources'][0]['PhysicalResourceId']
        start_time = datetime.datetime.now()
        try:
            waiter.wait(TargetGroupArn=target_group)
        except botocore.exceptions.WaiterError:
            print('Health check did not pass!')
            response = cloudformation.describe_stack_resources(
                StackName=version_stack_name,
                LogicalResourceId='ECSService'
            )
            service = response['StackResources'][0]['PhysicalResourceId']
            print('Outputting events for service {}:'.format(service))
            response = cloudformation.describe_stack_resources(
                StackName="ECS-{}".format(app_name),
                LogicalResourceId='ECSCluster'
            )
            cluster = response['StackResources'][0]['PhysicalResourceId']
            response = ecs.describe_services(
                cluster=cluster,
                services=[service]
            )
            for event in [x['message'] for x in response['services'][0]['events']]:
                print(event)
#            print('Deleting CloudFormation stack...')
#            response = cloudformation.delete_stack(
#                StackName="MV-{realm}-{app_name}-{version}-{env}".format(env=os.environ['ENV'], app_name=os.environ['ECS_APP_NAME'], version=os.environ['BUILD_VERSION'], realm=os.environ['REALM'])
#            )
#            waiter = cf.get_waiter('stack_delete_complete')
#            waiter.wait(
#                StackName="MV-{realm}-{app_name}-{version}-{env}".format(env=os.environ['ENV'], app_name=os.environ['ECS_APP_NAME'], version=os.environ['BUILD_VERSION'], realm=os.environ['REALM'])
#            )
#            print('CloudFormation stack deleted.')
        elapsed_time = datetime.datetime.now() - start_time
        print('Health check passed in {}'.format(elapsed_time))
        print("Done.")


def main():
    """Entrypoint for CLI"""

    template_path = os.environ.get('ECS_APP_VERSION_TEMPLATE_PATH', '/scripts/ecs-cluster-application-version.yml')
    app_name = os.environ['ECS_APP_NAME']
    env = os.environ['ENV']
    realm = os.environ['ENV']
    cluster_name = os.environ['ECS_CLUSTER_NAME']
    version = os.environ['BUILD_VERSION']
    aws_hosted_zone = os.environ['AWS_HOSTED_ZONE']
    base_path = os.environ['BASE_PATH']

    config = yaml.safe_load(open('deployment/ecs-config-env.yml', 'r').read())
    task_definition = json.loads(open('deployment/ecs-env.json', 'r').read())
    template = open(template_path, 'r').read()

    deploy_ecs_service(app_name=app_name, env=env, realm=realm, cluster_name=cluster_name, version=version, aws_hosted_zone=aws_hosted_zone, base_path=base_path, config=config, task_definition=task_definition, template=template)


if __name__ == "__main__":
    main()
