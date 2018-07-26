#!/usr/bin/env python3
"""
CLI tool and function for changing the default rule of an ALB to point to a TG
"""

import os
import datetime
import boto3
from autocleanup import get_alb_default_target_group

def get_cluster_full_name(cluster_name):
    ecs = boto3.client('ecs')
    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stack_resources(
        StackName="ECS-{}".format(cluster_name),
        LogicalResourceId='ECSCluster'
    )
    cluster = response['StackResources'][0]['PhysicalResourceId']
    return cluster


def get_current_count(cluster_name, service_full_name, cluster_full_name=None):
    """Get the number of active tasks for the version of the service being deployed"""

    if cluster_full_name is None:
        cluster_full_name = get_cluster_full_name(cluster_name)

    ecs = boto3.client('ecs')
    response = ecs.describe_services(
        cluster=cluster_full_name,
        services=[service_full_name])
    return response['services'][0]['runningCount']


def get_live_desired_count(cluster_name, app_name, cluster_full_name=None, next_token=None):
    """For a given app, loop through all services in the cluster and return the desired count for the live service. Recursively calls itself to loop through list_service pagination."""

    if cluster_full_name is None:
        cluster_full_name = get_cluster_full_name(cluster_name)

    live_service = None
    ecs = boto3.client('ecs')
    default_target_group = get_alb_default_target_group(cluster_name, app_name)
    kwargs = {
        'cluster': cluster_full_name,
        'launchType': 'EC2',
    }
    if next_token is not None:
        kwargs['nextToken'] = next_token
    response = ecs.list_services(**kwargs)
    next_token = response.get('nextToken')
    services = [x.split('/')[-1] for x in response['serviceArns']]  # returned data is ARN, we just want the name
    response = ecs.describe_services(
        cluster=cluster_full_name,
        services=services)

    for service in response['services']:
        if len(service['loadBalancers']) > 0:
            if service['loadBalancers'][0]['targetGroupArn'] == default_target_group:
                live_service = service

    if live_service is not None:
        return live_service['desiredCount']
    elif next_token is not None:
        return get_live_desired_count(cluster_name=cluster_name, cluster_full_name=cluster_full_name, app_name=app_name, next_token=next_token)


def set_correct_service_size(cluster_name, app_name, version_stack_name, target_group):
    cluster_full_name = get_cluster_full_name(cluster_name)
    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stack_resources(
        StackName=version_stack_name,
        LogicalResourceId='ECSServiceLB'
    )
    service_full_name = response['StackResources'][0]['PhysicalResourceId'].split('/')[-1]

    desired_count = get_live_desired_count(cluster_name=cluster_name, cluster_full_name=cluster_full_name, app_name=app_name)
    current_count = get_current_count(cluster_name=cluster_name, cluster_full_name=cluster_full_name, service_full_name=service_full_name)
    print('Live service has {} tasks, this version has {}.'.format(desired_count, current_count))
    if current_count >= desired_count:
        print('Number of running tasks ({}) is already correct.'.format(current_count))
        return
    print('Updating this version to match.')
    ecs = boto3.client('ecs')
    response = ecs.update_service(
        cluster=cluster_full_name,
        service=service_full_name,
        desiredCount=desired_count
    )

    elbv2 = boto3.client('elbv2')
    waiter = elbv2.get_waiter('target_in_service')
    start_time = datetime.datetime.now()
    try:
        response = waiter.wait(TargetGroupArn=target_group)
    except botocore.exceptions.WaiterError:
        print('Health check did not pass!')

    response = elbv2.describe_target_health(TargetGroupArn=target_group)
    targets = len([x for x in response['TargetHealthDescriptions'] if x['TargetHealth']['State'] == 'healthy'])
    elapsed_time = datetime.datetime.now() - start_time
    print('Health check passed in {}'.format(elapsed_time))
    print('There are now {} healthy tasks.'.format(targets))
    assert targets >= desired_count


def change_default_rule_tg(env, realm, cluster_name, app_name, version, aws_hosted_zone, base_path):
    version_stack_name = "ECS-{cluster_name}-App-{app_name}-{version}".format(
        cluster_name=cluster_name,
        app_name=app_name,
        version=version
    )
    alb_stack_name = 'ECS-{cluster_name}-App-{app_name}'.format(
        env=env,
        cluster_name=cluster_name,
        app_name=app_name,
        realm=realm
    )

    print('Beginning cutover for {}'.format('https://' + aws_hosted_zone + base_path))
    print('Changing default listener rule cutover...')
    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stack_resources(
        StackName=alb_stack_name,
        LogicalResourceId='ALBListenerSSL'
    )
    alb_listener = response['StackResources'][0]['PhysicalResourceId']
    print('ALB ARN is: {}'.format(alb_listener))

    response = cloudformation.describe_stack_resources(
        StackName=version_stack_name,
        LogicalResourceId='ALBTargetGroup'
    )
    target_group = response['StackResources'][0]['PhysicalResourceId']
    print('Target Group ARN is: {}'.format(target_group))

    set_correct_service_size(cluster_name=cluster_name, app_name=app_name, version_stack_name=version_stack_name, target_group=target_group)

    elbv2 = boto3.client('elbv2')
    response = elbv2.modify_listener(
        ListenerArn=alb_listener,
        DefaultActions=[
            {
                'Type': 'forward',
                'TargetGroupArn': target_group
            }
        ]
    )
    print('{} has been updated.'.format('https://' + aws_hosted_zone + base_path))


def main():
    """CLI entrypoint for cutover.py"""

    env = os.environ['ENV']
    realm = os.environ['REALM']
    cluster_name = os.environ['ECS_CLUSTER_NAME']
    app_name = os.environ['ECS_APP_NAME']
    version = os.environ['BUILD_VERSION']
    aws_hosted_zone = os.environ['AWS_HOSTED_ZONE']
    base_path = os.environ['BASE_PATH']
    change_default_rule_tg(env=env, realm=realm, cluster_name=cluster_name, app_name=app_name, version=version, aws_hosted_zone=aws_hosted_zone, base_path=base_path)


if __name__ == "__main__":
    main()
