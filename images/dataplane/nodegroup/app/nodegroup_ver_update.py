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
import logging
import os
import json
import sys
import cfnresponse


class ConfigKey:
    cluster_name_key = 'EksClusterName'
    cluster_version_key = 'EksUpdateClusterVersion'
    node_group_key = 'EksNodeGroup'
    launch_template_name = 'EksNodeGroupTemplateName'
    launch_template_version = 'EksNodeGroupTemplateVersion'


# logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

logger.info('starting run...')
current_region = os.environ['AWS_REGION']
logger.info(f'current region is: {current_region}')
session_name = 'EKS_UPDATE_NODE_SESSION'

config_dict = {
    ConfigKey.cluster_name_key: os.environ[ConfigKey.cluster_name_key],
    ConfigKey.cluster_version_key: os.environ[ConfigKey.cluster_version_key],
    ConfigKey.node_group_key: os.environ[ConfigKey.node_group_key],
    ConfigKey.launch_template_name: os.environ[ConfigKey.launch_template_name],
    ConfigKey.launch_template_version: os.environ[ConfigKey.launch_template_version]
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
    node_group_name = config_dict[ConfigKey.node_group_key]
    launch_template_name = config_dict[ConfigKey.launch_template_name]
    launch_template_version = config_dict[ConfigKey.launch_template_version]
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
    logger.info('run eksctl enable logs command')
    output = subprocess.run(
        f'/usr/local/bin/eksctl utils update-cluster-logging --cluster {cluster_name} --enable-types=controllerManager --approve',
        encoding='utf-8', capture_output=True, shell=True)
    command_output = get_stdout(output)
    logger.info(f'enable cluster control plane logs: {command_output}')

    # describe nodegroup
    logger.info('run awscli to update nodegroup template version')
    if cluster_version:
        update_nodegroup_version = f'aws eks update-nodegroup-version  --cluster-name {cluster_name} --nodegroup-name {node_group_name} --kubernetes-version {cluster_version} --launch-template name={launch_template_name},version={launch_template_version}'
    else:
        update_nodegroup_version = f'aws eks update-nodegroup-version  --cluster-name {cluster_name} --nodegroup-name {node_group_name} --launch-template name={launch_template_name},version={launch_template_version}'

    output = subprocess.run(f'{update_nodegroup_version}', encoding='utf-8', capture_output=True, shell=True)
    command_output = get_stdout(output)
    logger.info(f'update nodegroup dataplane output: {command_output}')
    update_nodegroup_desc = json.loads(command_output)
    return update_nodegroup_desc['update']['id']


def handler(event, context):
    try:
        logger.info(f'argurments {str(sys.argv)}')
        response_data = {}
        if event['RequestType'] == 'Create' or event['RequestType'] == 'Update':
            update_id = update_cluster(config_dict)
            response_data = {'UpdateID': update_id}
            status = cfnresponse.SUCCESS
        elif event['RequestType'] == 'Delete':
            status = cfnresponse.SUCCESS
        cfnresponse.send(event, context, status, response_data)
    except Exception as ex:
        logger.error(ex)
        cfnresponse.send(event, context, cfnresponse.FAILED, None)
    logger.info('ending run...')
