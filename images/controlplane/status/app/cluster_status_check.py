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
    signal_url = 'SignalUrl'
    cluster_version_key = 'EksUpdateClusterVersion'

# logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

logger.info('starting run...')

current_region = os.environ['AWS_REGION']
logger.info(f'current region is: {current_region}')

session_name = 'EKS_UPDATE_SESSION'

config_dict = {
    ConfigKey.cluster_name_key: os.environ[ConfigKey.cluster_name_key],
    ConfigKey.signal_url: os.environ[ConfigKey.signal_url],
    ConfigKey.cluster_version_key: os.environ[ConfigKey.cluster_version_key]
}

logger.info(config_dict)

kube_config_path = '/tmp/kubeconfig'

os.environ['KUBECONFIG'] = kube_config_path


def get_update_version(update_desc):
    for param in update_desc['update']['params']:
        if param['type'] == 'Version':
            return param['value']


def send_update(status):
    try:
        payload = '{"Status" : "' + status + '","Reason" : "Configuration ' + status + '","UniqueId" : "ID1234","Data" : "Application has completed configuration."}'
        r = requests.put(config_dict[ConfigKey.signal_url], data=payload)
    except Exception as ex:
        logger.exception(ex)


def handler(event, context):
    try:
        eks = boto3.client('eks')
        response = eks.list_updates(name=config_dict[ConfigKey.cluster_name_key])
        for update_id in response['updateIds']:
            update_desc = eks.describe_update(
                name=config_dict[ConfigKey.cluster_name_key], updateId=update_id)
            update_type = update_desc['update']['type']
            if update_type == 'VersionUpdate':
                update_status = update_desc['update']['status']
                update_version = get_update_version(update_desc)
                if update_version == config_dict[ConfigKey.cluster_version_key]:
                    if update_status == 'Successful':
                        send_update('SUCCESS')
                    else:
                        logger.info(f'Control Plane upgrade is: {update_status} update id is: {update_id}')
                else:
                    logger.info(f'Control Plane EKS version found :{update_version}')
        try:        
            if event['RequestType'] is not None:
                if event['RequestType'] == 'Create' or event['RequestType'] == 'Update' or event['RequestType'] == 'Delete':
                    status = cfnresponse.SUCCESS 
                    cfnresponse.send(event, context, status,None)    
        except Exception as ex:
            pass                    
    except Exception as ex:
        logger.exception(ex)
        send_update("FAILURE")
        status = cfnresponse.FAILED 
        cfnresponse.send(event, context, status,None) 
    logger.info('ending run...')
