"""
Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import boto3
import os
import logging
import requests
import cfnresponse


class ConfigKey:
    cluster_name_key = 'EksClusterName'
    node_group_key = 'EksNodeGroup'
    launch_template_name = 'EksNodeGroupTemplateName'
    launch_template_version = 'EksNodeGroupTemplateVersion'
    signal_url = 'SignalUrl'
    update_id = 'UpdateID'


# logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

logger.info('starting run...')
current_region = os.environ['AWS_REGION']
logger.info(f'current region is: {current_region}')
session_name = 'EKS_UPDATE_SESSION'

config_dict = {
    ConfigKey.cluster_name_key: os.environ[ConfigKey.cluster_name_key],
    ConfigKey.node_group_key: os.environ[ConfigKey.node_group_key],
    ConfigKey.launch_template_name: os.environ[ConfigKey.launch_template_name],
    ConfigKey.launch_template_version: os.environ[ConfigKey.launch_template_version],
    ConfigKey.signal_url: os.environ[ConfigKey.signal_url],
    ConfigKey.update_id: os.environ[ConfigKey.update_id],
}

logger.info(config_dict)
kube_config_path = '/tmp/kubeconfig'
os.environ['KUBECONFIG'] = kube_config_path


def get_update(update_desc, update_type):
    for param in update_desc['update']['params']:
        if param['type'] == update_type:
            return param['value']


def handler(event, context):
    try:
        eks = boto3.client('eks')
        eks.list_updates(name=config_dict[ConfigKey.cluster_name_key],
                         nodegroupName=config_dict[ConfigKey.node_group_key])
        update_id = config_dict[ConfigKey.update_id]
        update_desc = eks.describe_update(name=config_dict[ConfigKey.cluster_name_key],
                                          updateId=config_dict[ConfigKey.update_id],
                                          nodegroupName=config_dict[ConfigKey.node_group_key])
        update_type = update_desc['update']['type']
        if update_type == 'VersionUpdate':
            update_status = update_desc['update']['status']
            update_template_name = get_update(update_desc, "LaunchTemplateName")
            update_template_version = get_update(update_desc, "LaunchTemplateVersion")
            if update_template_name == config_dict[ConfigKey.launch_template_name] and update_template_version == \
                    config_dict[ConfigKey.launch_template_version]:
                if update_status == 'Successful':
                    payload = '{"Status" : "SUCCESS","Reason" : "Configuration Complete","UniqueId" : "ID1234","Data" : "Application has completed configuration."}'
                    requests.put(config_dict[ConfigKey.signal_url], data=payload)
                    logger.info(f'Nodegroup upgrade Completed. update id is: {update_id}')
                elif update_status == 'Failed':
                    payload = '{"Status" : "FAILURE","Reason" : "Update Failed","UniqueId" : "ID1235","Data" : "Application has completed configuration."}'
                    requests.put(config_dict[ConfigKey.signal_url], data=payload)
                    logger.info(f'Nodegroup upgrade Failed. update id is: {update_id}')
                else:
                    logger.info(f'Nodegroup upgrade In Progress. update id is: {update_id}')
            else:
                logger.info(f'Nodegroup EKS version found :{update_template_version}')
        try:
            if event['RequestType'] is not None:
                if event['RequestType'] == 'Create' or event['RequestType'] == 'Update' or \
                        event['RequestType'] == 'Delete':
                    status = cfnresponse.SUCCESS
                    cfnresponse.send(event, context, status, None)
        except Exception:
            pass
    except Exception as ex:
        logger.error(ex)
        payload = '{"Status" : "FAILURE","Reason" : "Configuration Complete","UniqueId" : "ID1234","Data" : "Application has completed configuration."}'
        requests.put(config_dict[ConfigKey.signal_url], data=payload)
        status = cfnresponse.FAILED
        cfnresponse.send(event, context, status, None)
    logger.info('ending run...')
