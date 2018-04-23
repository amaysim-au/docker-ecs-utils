#!/usr/bin/env python3
import sys, os
import boto3, botocore
from pprint import pprint
from deploy import get_list_of_rules

def cleanup_version_stack():
    cloudformation = boto3.client('cloudformation')

    version_stack_name = "ECS-{cluster_name}-App-{app_name}-{version}".format(
        cluster_name=os.environ['ECS_CLUSTER_NAME'],
        app_name=os.environ['ECS_APP_NAME'],
        version=os.environ['BUILD_VERSION']
    )
    alb_stack_name = 'ECS-{cluster_name}-App-{app_name}'.format(
        env=os.environ['ENV'],
        cluster_name=os.environ['ECS_CLUSTER_NAME'],
        app_name=os.environ['ECS_APP_NAME'],
        realm=os.environ['REALM']
    )

    alb_default_target_group = ""

    rules = get_list_of_rules()
    for rule in rules:
        if rule['IsDefault'] == True:
            alb_default_target_group = rule['Actions'][0]['TargetGroupArn']
            break

    if alb_default_target_group == "":
        raise Exception("Default action target group not found in ALB Listener")

    # Fetching Application Version TargetGroup ARN
    response = cloudformation.describe_stack_resources(
        StackName=version_stack_name,
        LogicalResourceId='ALBTargetGroup'
    )
    target_group = response['StackResources'][0]['PhysicalResourceId']
    print('Target Group ARN is: {}'.format(target_group))

    if target_group == alb_default_target_group:
        # Cannot cleanup, target group is in use
        print("Error: Cannot cleanup, version {version} is live".format(version=os.environ['BUILD_VERSION']))
        sys.exit(1)

    response = cloudformation.delete_stack(
        StackName=version_stack_name
    )

    waiter = cloudformation.get_waiter('stack_delete_complete')

    print("Deleting stack: {}".format(version_stack_name))
    try:
        waiter.wait(StackName=version_stack_name)
    except botocore.exceptions.WaiterError:
        print('Could not delete version stack!')
        print('Outputting events for stack {}:'.format(version_stack_name))
        response = cloudformation.describe_stack_events(
            StackName=version_stack_name
        )

        for stack_event in response['StackEvents'][::-1]:
            if 'ResourceStatusReason' not in stack_event:
                stack_event['ResourceStatusReason'] = ""

            print("{resource_status} {logical_resource_id} {resource_status_reason}".format(
                resource_status=stack_event['ResourceStatus'],
                logical_resource_id=stack_event['LogicalResourceId'],
                resource_status_reason=stack_event['ResourceStatusReason']
                )
            )

    print('Stack deletion complete')

if __name__ == "__main__":
    cleanup_version_stack()
