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

import logging
import os
import subprocess
import sys
import boto3
import cfnresponse


class ConfigKey:
    cluster_name_key = 'EksClusterName'
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
    ConfigKey.cluster_version_key: os.environ[ConfigKey.cluster_version_key]
}

logger.info(config_dict)

kube_config_path = '/tmp/kubeconfig'

os.environ['KUBECONFIG'] = kube_config_path


def get_stdout(output):
    """
    validates command output returncode and returns stdout
    """
    logger.info(output)
    if output.returncode == 0:
        command_output = output.stdout
    else:
        raise Exception(f'Command failed for - stderr: {output.stderr} - returncode: {output.returncode}')
    return command_output


def update_cluster(config_dict):
    cluster_name = config_dict[ConfigKey.cluster_name_key]
    cluster_version = config_dict[ConfigKey.cluster_version_key]

    logger.info(f'Cluster found, named: {config_dict[ConfigKey.cluster_name_key]}')

    # write config
    configure_cli = f'aws eks update-kubeconfig --name {cluster_name}'
    output = subprocess.run(f'{configure_cli}', encoding='utf-8', capture_output=True, shell=True)
    if output.returncode != 0:
        raise RuntimeError(f'Falied to create kube config file {output.stderr}.')
    logger.info('Create kube config file.')

    # updates existing config file
    output = subprocess.run(['/usr/local/bin/eksctl', 'utils', 'write-kubeconfig', '--cluster', cluster_name],
                            encoding='utf-8', capture_output=True)
    logger.info(output)

    # update .kube/config for aws2 version of cli
    subprocess.run(['sed', '-i', '-e', 's/command: aws/command: \/usr\/local\/bin\/aws/g', kube_config_path],
                   encoding='utf-8', capture_output=True)

    # enable cluster logs
    eks = boto3.client('eks')
    response = eks.describe_cluster(name=config_dict[ConfigKey.cluster_name_key])

    update_status = response['cluster']['status']
    if update_status == 'ACTIVE':
        logger.info('run eksctl enable logs command')
        output = subprocess.run(
            f'/usr/local/bin/eksctl utils update-cluster-logging --cluster {cluster_name} --enable-types=controllerManager --approve',
            encoding='utf-8', capture_output=True, shell=True)
        command_output = get_stdout(output)
        logger.info(f'enable cluster control plane logs: {command_output}')

        # upgrade eksctl cluster
        logger.info('run eksctl upgrade control plane command')
        output = subprocess.run(
            f'/usr/local/bin/eksctl upgrade cluster --name={cluster_name} --version={cluster_version} --approve',
            encoding='utf-8', capture_output=True, shell=True)
        command_output = get_stdout(output)
        logger.info(f'update cluster control plane: {command_output}')
    elif update_status == 'UPDATING':
        logger.info('Cluster is already updating')
    else:
        logger.info(f'Cluster not in upgrading status - : {update_status}')


def handler(event, context):
    try:
        logger.info(f'argurments {str(sys.argv)}')
        if event['RequestType'] == 'Create' or event['RequestType'] == 'Update':
            update_cluster(config_dict)
            status = cfnresponse.SUCCESS
        elif event['RequestType'] == 'Delete':
            status = cfnresponse.SUCCESS
        cfnresponse.send(event, context, status, None)
    except Exception as ex:
        logger.error(ex)
        cfnresponse.send(event, context, cfnresponse.FAILED, None)
    logger.info('ending run...')
