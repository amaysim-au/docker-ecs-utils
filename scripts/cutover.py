#!/usr/bin/env python3
import sys, os
import boto3, botocore


def change_default_rule_tg():
    version_stack_name = "MV-{realm}-{app_name}-{version}-{env}".format(
        env=os.environ['ENV'],
        app_name=os.environ['ECS_APP_NAME'],
        version=os.environ['BUILD_VERSION'],
        realm=os.environ['REALM']
    )
    alb_stack_name = 'ECS-{cluster_name}-App-{app_name}'.format(
        env=os.environ['ENV'],
        cluster_name=os.environ['ECS_CLUSTER_NAME'],
        app_name=os.environ['ECS_APP_NAME'],
        realm=os.environ['REALM']
    )

    print('Beginning default listener rule cutover...')
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
    print('Done.')


if __name__ == "__main__":
    change_default_rule_tg()
