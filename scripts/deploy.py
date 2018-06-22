#!/usr/bin/env python3

import sys, os, yaml, json, datetime
import boto3, botocore
import unittest
from unittest.mock import patch
import re
import time



class GetPriorityTest(unittest.TestCase):
    def test_1(self):
        """Simple test to get next priority"""
        rules = json.loads('[{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:listener-rule/app/asdfasdfasdf/ba564ec55606a717/9c431593f1c78965/2cc6c973c4d32f55","Priority":"1","Conditions":[{"Field":"host-header","Values":["host1.asdf.com"]},{"Field":"path-pattern","Values":["/path2"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:listener-rule/app/asdfasdfasdf/ba564ec55606a717/9c431593f1c78965/f9994e3e3a55d6dd","Priority":"2","Conditions":[{"Field":"path-pattern","Values":["/path1"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:listener-rule/app/asdfasdfasdf/ba564ec55606a717/9c431593f1c78965/74a74e7da03f7ddb","Priority":"default","Conditions":[],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":true}]')
        priority = get_priority(rules)
        self.assertEqual(priority, 3)

    def test_2(self):
        """Test with gap in list of priorities"""
        rules = json.loads('[{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:listener-rule/app/asdfasdfasdf/ba564ec55606a717/9c431593f1c78965/5cdf34d5cf48fabc","Priority":"1","Conditions":[{"Field":"path-pattern","Values":["/asdffdas"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:listener-rule/app/asdfasdfasdf/ba564ec55606a717/9c431593f1c78965/2cc6c973c4d32f55","Priority":"2","Conditions":[{"Field":"host-header","Values":["host1.asdf.com"]},{"Field":"path-pattern","Values":["/path2"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:listener-rule/app/asdfasdfasdf/ba564ec55606a717/9c431593f1c78965/284a6e35adc73d71","Priority":"5","Conditions":[{"Field":"path-pattern","Values":["/32452345"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:listener-rule/app/asdfasdfasdf/ba564ec55606a717/9c431593f1c78965/74a74e7da03f7ddb","Priority":"default","Conditions":[],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":true}]')
        priority = get_priority(rules)
        self.assertEqual(priority, 3)

    def test_3(self):
        """Test with no rules except default"""
        rules = json.loads('[{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:listener-rule/app/asdfasdfasdf/ba564ec55606a717/9c431593f1c78965/74a74e7da03f7ddb","Priority":"default","Conditions":[],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:12345678987:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":true}]')
        priority = get_priority(rules)
        self.assertEqual(priority, 1)


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

cf = boto3.client('cloudformation')

def create_or_update_stack(stack_name, template, parameters, tags):
    'Update or create stack'

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
            stack_result = cf.update_stack(**params)
            waiter = cf.get_waiter('stack_update_complete')
        else:
            print('Creating {}'.format(stack_name))
            stack_result = cf.create_stack(**params)
            waiter = cf.get_waiter('stack_create_complete')
        print("...waiting for stack to be ready...")
        waiter.wait(StackName=stack_name)
    except botocore.exceptions.ClientError as ex:
        error_message = ex.response['Error']['Message']
        if error_message == 'No updates are to be performed.':
            print("No changes")
        else:
            raise
    else:
        return cf.describe_stacks(StackName=stack_result['StackId'])


def _parse_template(template):
    cf.validate_template(TemplateBody=template)
    return template


def _stack_exists(stack_name):
    try:
        response = cf.describe_stacks(
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


class GenerateEnvironmentObjectTest(unittest.TestCase):
    @patch('builtins.open', unittest.mock.mock_open(read_data="ENV\nREALM\nECS_APP_NAME\nAWS_SECRET_ACCESS_KEY"))
    @patch.dict('os.environ', {'ENV': 'Dev', 'REALM': 'NonProd', 'AWS_SECRET_ACCESS_KEY': "I should not be present"})
    def test_1(self):
        """Test with variables present in .env and in working environment"""
        expected_environment = [
            {
                "name": "ENV",
                "value": "Dev"
            },
            {
                "name": "REALM",
                "value": "NonProd"
            },
            {
                "name": "ECS_APP_NAME",
                "value": ""
            }
        ]
        environment = generate_environment_object()
        self.assertEqual(environment, expected_environment)

    @patch('builtins.open', unittest.mock.mock_open(read_data="ENV\n\n\nREALM\n#asdfasdf\nECS_APP_NAME\nAWS_SECRET_ACCESS_KEY"))
    @patch.dict('os.environ', {'ENV': 'asdfsa!!asdfasdf#asdf', 'REALM': '""asdf\'asdfdfas{"asdf":"asdfa\'sd"}', 'AWS_SECRET_ACCESS_KEY': "I should not be present #          "})
    def test_2(self):
        """Test with weird formatting and characters in .env"""
        expected_environment = [
            {
                "name": "ENV",
                "value": "asdfsa!!asdfasdf#asdf"
            },
            {
                "name": "REALM",
                "value": '""asdf\'asdfdfas{"asdf":"asdfa\'sd"}'
            },
            {
                "name": "ECS_APP_NAME",
                "value": ""
            }
        ]
        environment = generate_environment_object()
        self.assertEqual(environment, expected_environment)

    @patch('builtins.open', unittest.mock.mock_open(read_data='ENV=\sdfsa!!asdfasdf#asdfn\n\nREALM=""asdf\'asdfdfas{"asdf":"asdfa\'sd"}\n#asdfasdf\nECS_APP_NAME=dddddd # comment\nAWS_SECRET_ACCESS_KEY'))
    @patch.dict('os.environ', {'ENV': 'asdfsa!!asdfasdf', 'REALM': '""asdf\'asdfdfas{"asdf":"asdfa\'sd"}', 'ECS_APP_NAME': 'dddddd', 'AWS_SECRET_ACCESS_KEY': "I should not be present #          "})
    def test_3(self):
        """Test with environment variable values set in file"""
        expected_environment = [
            {
                "name": "ENV",
                "value": "asdfsa!!asdfasdf"
            },
            {
                "name": "REALM",
                "value": '""asdf\'asdfdfas{"asdf":"asdfa\'sd"}'
            },
            {
                "name": "ECS_APP_NAME",
                "value": "dddddd"
            }
        ]
        environment = generate_environment_object()
        self.assertEqual(environment, expected_environment)


def generate_environment_object():
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
        if env not in whitelisted_vars and env != '' and not re.match(r'^\s?#', env):
            environment.append(
                {
                    "name": env,
                    "value": os.environ.get(env, "")
                }
            )
    return environment

def get_list_of_rules():
    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stack_resources(
        StackName='ECS-{cluster_name}-App-{app_name}'.format(
            cluster_name=os.environ['ECS_CLUSTER_NAME'],
            app_name=os.environ['ECS_APP_NAME']),
        LogicalResourceId='ALBListenerSSL'
    )
    alb_listener = response['StackResources'][0]['PhysicalResourceId']

    client = boto3.client('elbv2')
    response = client.describe_rules(ListenerArn = alb_listener)
    return response['Rules']


def get_load_balancer_type(app_stack_name):
    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stacks(
        StackName=app_stack_name
    )
    try:
        load_balancer_type = [parameter['ParameterValue'] for parameter in response['Stacks'][0]['Parameters'] if parameter['ParameterKey'] == "LBType"][0]
    except:
        print('Could not find LBType parameter in response: {}'.format(response))
    return load_balancer_type


def main():
    print("Beginning deployment of {}...".format(os.environ['ECS_APP_NAME']))

    template_path = os.environ.get('ECS_APP_VERSION_TEMPLATE_PATH', '/scripts/ecs-cluster-application-version.yml')
    version_stack_name = "ECS-{cluster_name}-App-{app_name}-{version}".format(
        cluster_name=os.environ['ECS_CLUSTER_NAME'],
        app_name=os.environ['ECS_APP_NAME'],
        version=os.environ['BUILD_VERSION']
    )
    app_stack_name = "ECS-{cluster}-App-{app}".format(cluster=os.environ['ECS_CLUSTER_NAME'], app=os.environ['ECS_APP_NAME'])

    load_balancer_type = get_load_balancer_type(app_stack_name)
    print("Load balancer type is {}.".format(load_balancer_type))

    print("Loading configuration files...")
    template = open(template_path, 'r').read()
    config = yaml.safe_load(open('deployment/ecs-config-env.yml','r').read())
    task_definition = json.loads(open('deployment/ecs-env.json','r').read())

    print("Generating environment variable configuration...")
    environment = generate_environment_object()
    for index, value in enumerate(task_definition['containerDefinitions']):
        task_definition['containerDefinitions'][index]['environment'] = environment
    print("Task definition generated:")
    print(json.dumps(task_definition, indent=2, default=str))

    print("Generating Parmeters for CloudFormation template ({})".format(template_path))
    if load_balancer_type != "None":  # this is intentionally a string
        container_port = [x['portMappings'][0]['containerPort'] for x in task_definition['containerDefinitions'] if x['name'] == os.environ['ECS_APP_NAME']][0]

    parameters = [
        {
            "ParameterKey": "Name",
            "ParameterValue": os.environ['ECS_APP_NAME']
        },
        {
            "ParameterKey": 'ClusterName',
            "ParameterValue": os.environ['ECS_CLUSTER_NAME']
        },
        {
            "ParameterKey": 'Environment',
            "ParameterValue": os.environ['ENV']
        },
        {
            "ParameterKey": 'Version',
            "ParameterValue": os.environ['BUILD_VERSION']
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
                "ParameterValue": os.environ['AWS_HOSTED_ZONE']
            },
            {
                "ParameterKey": 'Path',
                "ParameterValue": os.environ['BASE_PATH']
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
        except:
            pass
        if listener_rule == None:
            rules = get_list_of_rules()
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
        if priority != None:
            parameters.append({
                "ParameterKey": 'RulePriority',
                "ParameterValue": str(priority)
            })
        else:
            parameters.append({
                "ParameterKey": 'RulePriority',
                "UsePreviousValue": True
            })

    if config.get('autoscaling') != None:
        parameters.append({
            "ParameterKey": 'Autoscaling',
            "ParameterValue": str(config['autoscaling'])
        })
    if config.get('autoscaling_target') != None:
        parameters.append({
            "ParameterKey": 'AutoscalingTargetValue',
            "ParameterValue": str(config['autoscaling_target'])
        })
    if config.get('autoscaling_max_size') != None:
        parameters.append({
            "ParameterKey": 'AutoscalingMaxSize',
            "ParameterValue": str(config['autoscaling_max_size'])
        })
    if config.get('autoscaling_min_size') != None:
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
            'Value': os.environ['ECS_APP_NAME']
        },
        {
            'Key': 'Environment',
            'Value': os.environ['ENV']
        },
        {
            'Key': 'Realm',
            'Value': os.environ['REALM']
        },
        {
            'Key': 'Version',
            'Value': os.environ['BUILD_VERSION']
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
                StackName="ECS-{}".format(os.environ['ECS_CLUSTER_NAME']),
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




if __name__ == "__main__":
#    unittest.main(verbosity=2)
    main()
