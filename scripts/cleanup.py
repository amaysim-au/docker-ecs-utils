#!/usr/bin/env python3
"""CLI and function for targeted cleanup"""

import os
import boto3
import botocore
from cutover import get_version_target_group
from cutover import get_alb_default_target_group


def cleanup_version_stack(cluster_name, app_name, version):
    """Main function for cleaning up a given version stack"""

    cloudformation = boto3.client('cloudformation')

    version_stack_name = "ECS-{cluster_name}-App-{app_name}-{version}".format(
        cluster_name=cluster_name,
        app_name=app_name,
        version=version
    )

    alb_default_target_group = get_alb_default_target_group(cluster_name, app_name)

    target_group = get_version_target_group(version_stack_name)

    if target_group == alb_default_target_group:
        # Cannot cleanup, target group is in use
        raise Exception("Cannot cleanup, version {version} is live".format(version=version))

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

            print(
                "{resource_status} {logical_resource_id} {resource_status_reason}".format(
                    resource_status=stack_event['ResourceStatus'],
                    logical_resource_id=stack_event['LogicalResourceId'],
                    resource_status_reason=stack_event['ResourceStatusReason']
                )
            )

    print('Stack deletion complete')

if __name__ == "__main__":
    cleanup_version_stack(cluster_name=os.environ['ECS_CLUSTER_NAME'], app_name=os.environ['ECS_APP_NAME'], version=os.environ['BUILD_VERSION'])
