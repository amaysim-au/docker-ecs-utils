#!/usr/bin/env python3

import sys, os, yaml, json, datetime
# import boto3
import subprocess
from pprint import pprint

if len(sys.argv) != 4 and len(sys.argv) != 3:
    exit('Usage: ./deploy.py <APP_NAME> <CLUSTER_NAME> [TASK_DEFINITION_IAM_ROLE]')

vpc_id = None
ecs_cluster = None
ecs_service_role = None
ecs_task_role = None
alb_listener = None
alb_listener_public = None

# Default
ecs_desired_tasks = 2

name = sys.argv[1]
cluster = sys.argv[2]

if len(sys.argv) == 4:
    ecs_task_role = sys.argv[3]

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

def read_ecs_config():
    lb_host = None
    lb_path = '/*'
    lb_health_check = None
    lb_deregistration_delay = "30"
    scheme = 'internal' # internal | public

    if not os.path.isfile("deployment/ecs-config-env.yml"):
        sys.exit('ERROR: File ecs-config-env.yml does not exist')

    with open("deployment/ecs-config-env.yml") as data_file:
        data = yaml.load(data_file)

    if 'lb_host' in data:
        lb_host = data['lb_host']

    if 'lb_path' in data:
        lb_path = data['lb_path']

    if 'lb_health_check' in data:
        lb_health_check = data['lb_health_check']

    if 'lb_deregistration_delay' in data:
        lb_deregistration_delay = str(data['lb_deregistration_delay'])

    if 'scheme' in data:
        scheme = data['scheme']

    if not lb_path or not lb_health_check:
        sys.exit('ERROR: lb_path and lb_health_check labels must be defined at ecs-config.yml')

    if scheme == 'public' and alb_listener_public == None:
        sys.exit('ERROR: this cluster is not open to public. Use scheme: internal')

    return {
        'lb_host': lb_host,
        'lb_path': lb_path,
        'lb_health_check': lb_health_check,
        'lb_deregistration_delay': lb_deregistration_delay,
        'scheme': scheme
    }

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


def should_rule_exist(rule, lb_paths, lb_hosts):
    # Given a rule is deployed, should it exist according to the configuration supplied?
    for condition in rule['Conditions']:
        if x['Field'] == 'path-pattern':
            if x['Values'][0] not in lb_paths:
                return False
        elif x['Field'] == 'host-header':
            if x['Values'][0] not in lb_hosts:
                return False


def does_rule_exist(rules, lb_path, lb_host):
    # Given a path (or a path and a host), is a rule currently deployed?
    for rule in rules:
        if lb_host != None:
            path_pattern = [x['Value'] for x in rule['Conditions'] if x['Field'] == 'path-pattern']
            host_header = [x['Value'] for x in rule['Conditions'] if x['Field'] == 'host-header']
            if lb_path in path_pattern and lb_host in host_header:
                return True
        else:
            path_pattern = [x['Value'] for x in rule['Conditions'] if x['Field'] == 'path-pattern']
            if lb_path in path_pattern:
                return True
    return False


def update_listener_rules(alb_listener, alb_target_group, lb_paths, lb_hosts):
    rules_json = subprocess.check_output("aws elbv2 describe-rules --listener-arn '"+alb_listener+"'", shell=True)
    rules = json.loads(rules_json)

    priorities = [x['Priority'] for x in rules['Rules'][0]]

    matching_rules = [x for x in rules['Rules'] if x['Actions'][0]['TargetGroupArn'] == alb_target_group]

    for rule in matching_rules:
        if not should_rule_exist(rule, lb_paths, lb_hosts):
            # delete rule

    for lb_host in lb_host:
        for lb_path in lb_paths:
            if does_rule_exist(rules, lb_path, lb_host):
                # update rule
            else:  # rule is not currently deployed, we must create it
                i = 1
                while not rule_priority:  # increment from 1 onwards until we find a priority that is unused
                    if not index in priorities:
                        rule_priority = index
                        priorities.append(rule_priority)
                    else:
                        i = i + 1
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
                # create rule


def create_task_definition(name):
    task_definition_name = cluster+"-"+name
    if ecs_task_role:
        command = "aws ecs register-task-definition --family "+task_definition_name+" --task-role-arn '"+ecs_task_role+"' --cli-input-json file://${PWD}/deployment/ecs-env.json"
    else:
        command = "aws ecs register-task-definition --family "+task_definition_name+" --cli-input-json file://${PWD}/deployment/ecs-env.json"

    result_json = subprocess.check_output(command, shell=True)
    result = json.loads(result_json)
    return result['taskDefinition']['taskDefinitionArn']

def create_alb_target_group(alb_listener, cluster, name):
    target_group_name = cluster+"-"+name

    result_json = subprocess.check_output("aws elbv2 create-target-group --name "+target_group_name+" --protocol HTTP --port 80 --vpc-id "+vpc_id+"", shell=True)
    result = json.loads(result_json)

    alb_target_group = result['TargetGroups'][0]['TargetGroupArn']

    return alb_target_group

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

def create_ecs_service(name, container_name, ecs_task_definition, alb_target_group, port, desired_tasks):
    lb = "targetGroupArn="+alb_target_group+",containerName="+container_name+",containerPort="+port
    command = "aws ecs create-service --cluster '"+ecs_cluster+"' --service-name '"+name+"' --load-balancers '"+lb+"' --task-definition '"+ecs_task_definition+"' --role '"+ecs_service_role+"' --desired-count "+str(desired_tasks)

    print("--> RUN: %s" % command)
    subprocess.check_output(command, shell=True)

    return name

def update_ecs_service(name, ecs_task_definition):
    command = "aws ecs update-service --cluster '"+ecs_cluster+"' --service '"+name+"' --task-definition '"+ecs_task_definition+"'"

    print("--> RUN: %s" % command)
    subprocess.check_output(command, shell=True)

def exists_ecs_service(name):
    result_json = subprocess.check_output("aws ecs describe-services --cluster "+ecs_cluster+" --services "+name, shell=True)
    result = json.loads(result_json)

    for service in result['services']:
        if service['status'] == 'ACTIVE':
            return True

    return False

def wait_ecs_service(name):
    print("--> Waiting for service to come online...")
    result_process = subprocess.Popen("aws ecs wait services-stable --cluster "+ecs_cluster+" --services "+name, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result_process.wait()

    if result_process.returncode == 255:
        print("--> ERROR - Service NOT stable after 10 minutes")

        result_json = subprocess.check_output("aws ecs describe-services --cluster "+ecs_cluster+" --services "+name, shell=True)
        result = json.loads(result_json)

        print("--> Last 10 events:")
        for event in result['services'][0]['events'][0:9]:
            created_at = datetime.datetime.utcfromtimestamp(event['createdAt']).strftime('%Y-%m-%dT%H:%M:%SZ')
            print("--> "+created_at+" "+event['message'])

        sys.exit(1)

def main():
    get_platform(cluster)
    config = read_ecs_config()

    ecs_task_definition = create_task_definition(name)
    print("--> Created Task Definition: %s" % ecs_task_definition)

    # Internal ALB Target Group
    alb_target_group = get_alb_target_group(cluster, name)

    if not alb_target_group:
        print("--> Creating ALB TargetGroup")
        alb_target_group = create_alb_target_group(alb_listener, cluster, name)
    else:
        print("--> Got ALB TargetGroup: %s" % alb_target_group)

    update_alb_target_group_params(alb_target_group, config['lb_deregistration_delay'])
    update_listener_rule(alb_listener, alb_target_group, config['lb_path'], config['lb_host'])
    update_target_group_health_check(alb_target_group, config['lb_health_check'])

    if not exists_ecs_service(name):
        print("--> Creating ECS Service")
        ecs_service = create_ecs_service(name, name, ecs_task_definition, alb_target_group, read_task_definition_port(), ecs_desired_tasks)
    else:
        print("--> Updating ECS Service")
        update_ecs_service(name, ecs_task_definition)

    wait_ecs_service(name)

    # Public ALB Target Group
    if config['scheme'] == 'public':
        name_public = 'public-'+name

        alb_target_group_public = get_alb_target_group(cluster, name_public)

        if not alb_target_group_public:
            print("--> Creating ALB TargetGroup (Public)")
            alb_target_group_public = create_alb_target_group(alb_listener, cluster, name_public)
        else:
            print("--> Got ALB TargetGroup (Public): %s" % alb_target_group_public)

        update_alb_target_group_params(alb_target_group_public, config['lb_deregistration_delay'])
        update_listener_rule(alb_listener_public, alb_target_group_public, config['lb_path'], config['lb_host'])
        update_target_group_health_check(alb_target_group_public, config['lb_health_check'])

        if not exists_ecs_service(name_public):
            print("--> Creating ECS Service (Public)")
            ecs_service_public = create_ecs_service(name_public, name, ecs_task_definition, alb_target_group_public, read_task_definition_port(), ecs_desired_tasks)
        else:
            print("--> Updating ECS Service (Public)")
            update_ecs_service(name_public, ecs_task_definition)

        wait_ecs_service(name_public)


if __name__ == "__main__":
    main()
