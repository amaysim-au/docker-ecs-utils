#!/usr/bin/env python3

import sys, os, yaml, json, datetime
import boto3, botocore
import subprocess
from pprint import pprint
import unittest
from unittest.mock import patch
from functools import reduce
import ruamel.yaml as yaml
import re


class GetPriorityTest(unittest.TestCase):
    def test_1(self):
        """Simple test to get next priority"""
        rules = json.loads('[{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:listener-rule/app/ECS-InternalTools-Dev/ba564ec55606a717/9c431593f1c78965/2cc6c973c4d32f55","Priority":"1","Conditions":[{"Field":"host-header","Values":["host1.asdf.com"]},{"Field":"path-pattern","Values":["/path2"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:listener-rule/app/ECS-InternalTools-Dev/ba564ec55606a717/9c431593f1c78965/f9994e3e3a55d6dd","Priority":"2","Conditions":[{"Field":"path-pattern","Values":["/path1"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:listener-rule/app/ECS-InternalTools-Dev/ba564ec55606a717/9c431593f1c78965/74a74e7da03f7ddb","Priority":"default","Conditions":[],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":true}]')
        priority = get_priority(rules)
        self.assertEqual(priority, 3)

    def test_2(self):
        """Test with gap in list of priorities"""
        rules = json.loads('[{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:listener-rule/app/ECS-InternalTools-Dev/ba564ec55606a717/9c431593f1c78965/5cdf34d5cf48fabc","Priority":"1","Conditions":[{"Field":"path-pattern","Values":["/asdffdas"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:listener-rule/app/ECS-InternalTools-Dev/ba564ec55606a717/9c431593f1c78965/2cc6c973c4d32f55","Priority":"2","Conditions":[{"Field":"host-header","Values":["host1.asdf.com"]},{"Field":"path-pattern","Values":["/path2"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:listener-rule/app/ECS-InternalTools-Dev/ba564ec55606a717/9c431593f1c78965/284a6e35adc73d71","Priority":"5","Conditions":[{"Field":"path-pattern","Values":["/32452345"]}],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":false},{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:listener-rule/app/ECS-InternalTools-Dev/ba564ec55606a717/9c431593f1c78965/74a74e7da03f7ddb","Priority":"default","Conditions":[],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":true}]')
        priority = get_priority(rules)
        self.assertEqual(priority, 3)

    def test_3(self):
        """Test with no rules except default"""
        rules = json.loads('[{"RuleArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:listener-rule/app/ECS-InternalTools-Dev/ba564ec55606a717/9c431593f1c78965/74a74e7da03f7ddb","Priority":"default","Conditions":[],"Actions":[{"Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:ap-southeast-2:434027879415:targetgroup/ecs-c-ALBDe-2TD7HNS9J92H/134e396d75ebd3a6"}],"IsDefault":true}]')
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


def create_or_update_stack(stack_name, template, parameters):
    'Update or create stack'

    template_data = _parse_template(template)

    params = {
        'StackName': stack_name,
        'TemplateBody': template_data,
        'Parameters': parameters,
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
        print(json.dumps(
            cf.describe_stacks(StackName=stack_result['StackId']),
            indent=2,
            default=json_serial
        ))


def _parse_template(template):
    cf.validate_template(TemplateBody=template)
    return template_data


def _stack_exists(stack_name):
    stacks = cf.list_stacks()['StackSummaries']
    for stack in stacks:
        if stack['StackStatus'] == 'DELETE_COMPLETE':
            continue
        if stack_name == stack['StackName']:
            return True
    return False


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError("Type not serializable")


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

def generate_environment_object():
    environment = []
    env_file = open('.env', 'r').read()
    for env in env_file.split('\n'):
        if env not in ["AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_ACCESS_KEY_ID", "AWS_SECURITY_TOKEN"] and env != '' and not re.match(r'^\s?#', env):
            environment.append(
                {
                    "name": env,
                    "value": os.environ.get(env, "")
                }
            )
    return environment


def main():
    template = open('/ecs-app.yml','r').read()
    config = yaml.safe_load(open('deployment/ecs-config.yml','r').read())
    task_definition = json.loads(open('deployment/ecs.json','r').read())

    environment = generate_environment_object()
    for index, value in enumerate(task_definition['containerDefinitions']):
        task_definition['containerDefinitions'][index]['environment'] = environment

    client = boto3.client('ecs')
    response = client.register_task_definition(
        family = '{app}-{env}'.format(app=config['app_name'], env=os.environ['ENV']),
        taskRoleArn = config['task_role_arn'],
        containerDefinitions=task_definition
    )
    config.append({'task_definition_arn': response['taskDefinition']['taskDefinitionArn']})

    parameters = {}  # what parameters will the template have?

    stack_name = "MV-{realm}-{app_name}-{version}-{env}".format(env=os.environ['ENV'], app_name=os.environ['ECS_APP_NAME'], version=os.environ['BUILD_VERSION'], realm=os.environ['REALM'])
    create_or_update_stack(stack_name, template, parameters)


if __name__ == "__main__":
#    unittest.main(verbosity=2)
    main()
