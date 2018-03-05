#!/usr/bin/env python3
import sys, os, yaml, json, datetime
import boto3, botocore
import ruamel.yaml as yaml
import re


def change_default_rule_tg():
    cloudformation = boto3.client('cloudformation')
    response = cloudformation.describe_stack_resources(
        StackName='ECS-{cluster_name}-App-{app_name}'.format(env=os.environ['ENV'], cluster_name=os.environment['CLUSTER_NAME'], app_name=os.environ['ECS_APP_NAME'], realm=os.environ['REALM']),
        LogicalResourceId='ALBListenerSSL'
    )
    alb_listener = response['StackResources'][0]['PhysicalResourceId']

    response = cloudformation.describe_stack_resources(
        StackName="MV-{realm}-{app_name}-{version}-{env}".format(env=os.environ['ENV'], app_name=os.environ['ECS_APP_NAME'], version=os.environ['BUILD_VERSION'], realm=os.environ['REALM'])
        LogicalResourceId='TargetGroup'
    )
    target_group = response['StackResources'][0]['PhysicalResourceId']

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
    return response


if __name__ == "__main__":
    change_default_rule_tg()
