#!/usr/bin/env python3

import sys, os, yaml, json, datetime
import boto3, botocore
import subprocess
from pprint import pprint
import unittest
from unittest.mock import patch
from functools import reduce
import jinja2
import ruamel.yaml as yaml

vpc_id = None
ecs_cluster = None
ecs_service_role = None
ecs_task_role = None
alb_listener = None
alb_listener_public = None

# Default
ecs_desired_tasks = 2

def get_platform(cluster):
    global vpc_id, ecs_service_role, ecs_cluster, alb_listener, alb_listener_public

    result_json = subprocess.check_output("aws cloudformation list-exports", shell=True)
    result = json.loads(result_json)

    for export in result['Exports']:
        if export['Name'] == "vpc":
            vpc_id = export['Value']
        elif export['Name'] == "ecs-"+cluster+"-ECSServiceRole":
            ecs_service_role = export['Value']
        elif export['Name'] == "ecs-"+cluster+"-ECSCluster":
            ecs_cluster = export['Value']
        elif export['Name'] == "ecs-"+cluster+"-ALBIntListenerSSL":
            alb_listener = export['Value']
        elif export['Name'] == "ecs-"+cluster+"-ALBPublicListenerSSL":
            alb_listener_public = export['Value']

def read_task_definition_port():
    with open("deployment/ecs-env.json") as data_file:
        data = json.load(data_file)

    try:
        port = data['containerDefinitions'][0]['portMappings'][0]['containerPort']
    except KeyError:
        sys.exit("ERROR: ecs.json: First container definition must have a containerPort")

    return str(port)

def update_target_group_health_check(alb_target_group, lb_health_check, lb_healthy_threshold=2):

    command = "aws elbv2 modify-target-group --target-group-arn '"+alb_target_group+"' --health-check-path '"+lb_health_check+"' --healthy-threshold-count "+str(lb_healthy_threshold)

    print("--> RUN: %s" % command)
    subprocess.check_output(command, shell=True)


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

def update_listener_rule(alb_listener, alb_target_group, lb_path, lb_host):
    rules_json = subprocess.check_output("aws elbv2 describe-rules --listener-arn '"+alb_listener+"'", shell=True)
    rules = json.loads(rules_json)

    rule_arn = None
    rule_priority = str(len(rules["Rules"]))

    for rule in rules["Rules"]:
        if rule["Actions"][0]["TargetGroupArn"] == alb_target_group:
            rule_arn = rule["RuleArn"]
            break

    conditions = []

    lb_path_condition = {
        "Field": "path-pattern",
        "Values": [lb_path]
    }
    conditions.append(lb_path_condition)

    if lb_host != None:
        lb_host_condition = {
            "Field": "host-header",
            "Values": [lb_host]
        }
        conditions.append(lb_host_condition)

    if rule_arn:
        command = "aws elbv2 modify-rule --rule-arn "+rule_arn+" --conditions '"+json.dumps(conditions)+"'"
    else:
        command = "aws elbv2 create-rule --listener-arn "+alb_listener+" --priority "+rule_priority+" --conditions '"+json.dumps(conditions)+"' --actions Type=forward,TargetGroupArn="+alb_target_group+""

    print("--> RUN: %s" % command)
    subprocess.check_output(command, shell=True)

def update_alb_target_group_params(alb_target_group, lb_deregistration_delay):
    subprocess.check_output("aws elbv2 modify-target-group-attributes --target-group-arn "+alb_target_group+" --attributes Key=deregistration_delay.timeout_seconds,Value="+lb_deregistration_delay, shell=True)


def get_alb_target_group(cluster, name):
    target_group_name = cluster+"-"+name

    result_process = subprocess.Popen("aws elbv2 describe-target-groups --names "+target_group_name, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result_process.wait()
    result_json,_ = result_process.communicate()
    if result_process.returncode == 255:
        return None

    result = json.loads(result_json)
    return result['TargetGroups'][0]['TargetGroupArn']


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


def main():
	template = open('/ecs-app.yml','r'),read()
	config = yaml.safe_load(open('deployment/ecs-config.yml','r'),read())
	task_definition = json.loads(open('deployment/ecs.json','r'),read())

    client = boto3.client('ecs')
    response = client.register_task_definition(
        family = '{app}-{env}'.format(app=config['app_name'], env=os.environ['ENV']),
        taskRoleArn = config['task_role_arn'],
        containerDefinitions=task_definition
    }
    config.append({'task_definition_arn': response['taskDefinition']['taskDefinitionArn']})
	rendered_template = jinja2.Template(template).render(config)

	parameters = {}  # what parameters will the template have?

    stack_name = "MV-{env}-{app_name}-{version}-{realm}".format(env=os.environ['ENV'], app_name=config['ecs_app_name'], version=os.environ['BUILD_VERSION'], realm=os.environ['REALM'])
	create_or_update_stack(stack_name, rendered_template, parameters)


if __name__ == "__main__":
#    unittest.main(verbosity=2)
    main()
