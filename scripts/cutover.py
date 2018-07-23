#!/usr/bin/env python3
"""
CLI tool and function for changing the default rule of an ALB to point to a TG
"""

import os
import boto3


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

    client = boto3.client('elbv2')
    response = client.modify_listener(
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
