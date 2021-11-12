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

import subprocess
import os
import logging
import sys
import cfnresponse


class ConfigKey:
    cluster_name_key = 'EksClusterName'
    name_space_key = 'EksNameSpace'
    daemon_key = 'EksDaemon'


# logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

logger.info('starting run...')

current_region = os.environ['AWS_REGION']
logger.info(f'current region is: {current_region}')

session_name = 'EKS_UPDATE_SESSION'

config_dict = {
    ConfigKey.cluster_name_key: os.environ[ConfigKey.cluster_name_key],
    ConfigKey.name_space_key: os.environ[ConfigKey.name_space_key],
    ConfigKey.daemon_key: os.environ[ConfigKey.daemon_key]
}

logger.info(config_dict)

# daemon_key valid values

ALLOWED_KEY_SET = set(["aws-node", "coredns", "kube-proxy"])

if config_dict[ConfigKey.daemon_key] not in ALLOWED_KEY_SET:
    raise ValueError(f'Invaild value: {config_dict[ConfigKey.daemon_key]} not in {str(ALLOWED_KEY_SET)}')

cluster_name = config_dict[ConfigKey.cluster_name_key]
logger.info(f'{cluster_name}')

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
    daemon = config_dict[ConfigKey.daemon_key]
    name_space = config_dict[ConfigKey.name_space_key]
    logger.info(f'Cluster found, named: {cluster_name}')

    # write config

    configure_cli = f'aws eks update-kubeconfig --name {cluster_name}'
    output = subprocess.run(f'{configure_cli}', encoding='utf-8', capture_output=True, shell=True)
    if output.returncode != 0:
        raise RuntimeError(f'Falied to create kube config file {output.stderr}.')
    logger.info('Create kube config file.')

    # update existing config file

    output = subprocess.run(['/usr/local/bin/eksctl', 'utils', 'write-kubeconfig', '--cluster', cluster_name],
                            encoding='utf-8', capture_output=True)
    logger.info(output)

    # update .kube/config for aws2 version of cli

    subprocess.run(['sed', '-i', '-e', 's/command: aws/command: \/usr\/local\/bin\/aws/g', kube_config_path],
                   encoding='utf-8', capture_output=True)

    # list pods

    output = subprocess.run(f'/usr/local/bin/kubectl get po -n {name_space}', encoding='utf-8', capture_output=True,
                            shell=True)
    command_output = get_stdout(output)

    daemon_pod_count = 0
    for line in command_output.split('\n'):
        if line.startswith(daemon):
            daemon_pod_count += 1

    output = subprocess.run(f'/usr/local/bin/eksctl utils update-{daemon} --cluster={cluster_name} --approve',
                            encoding='utf-8', capture_output=True, shell=True)

    command_output = get_stdout(output)
    logger.info(f'update-{daemon}: {command_output}')

    return daemon_pod_count


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
