import click
import boto3
from environs import Env
import os

env = Env()
env.read_env()

local_file_directory = 'data'

@click.command()
@click.option('--add-aws', default='', help="Add a node to the swarm. Syntax: add-aws gpu-node | mpi-node")
@click.option('--add-dalco', default='', help="Add a node to the swarm. Syntax: add-dalco gpu-node | mpi-node")
@click.option('--remove', default='', help='Remove a node from the swarm. Syntax:  remove node-id')
@click.option('--list-instances', is_flag=True, help='List aws instances')
@click.option('--list-nodes', is_flag=True, help='List nodes from the swarm')

def cli(add_aws, add_dalco, remove,list_nodes, list_instances):
    if list_nodes:
        stream = os.popen('ssh -i /home/ubuntu/osparc-staging.pem -oStrictHostKeyChecking=no ubuntu@staging.osparc.io "docker node ls"')
        output = stream.read()
        print(output)
    if list_instances:
        ec2 = boto3.resource('ec2')
        for instance in ec2.instances.all():
            print(
                "Id: {0}\nName {1}\nType: {2}\nPublic IPv4: {3}\nAMI: {4}\nState: {5}\n".format(
                instance.tags, instance.platform, instance.instance_type, instance.public_ip_address, instance.image.id, instance.state
                )
            )
    if add_aws:
        if add_aws == "gpu-node":
            start_instance_aws("ami-0991c617d8542ca34", "g4dn.xlarge", "DemOsparc GPU")
        elif add_aws == "mpi-node":
            start_instance_aws("ami-0edec1024f4ac92f5", "c5a.2xlarge", "DemOsparc MPI")

    if add_dalco:
        if add_dalco == "gpu-node":
            start_instance_dalco("ami-0991c617d8542ca34", "g4dn.xlarge", "DemOsparc GPU")
        elif add_dalco == "mpi-node":
            start_instance_dalco("ami-0edec1024f4ac92f5", "c5a.2xlarge", "DemOsparc MPI")

    if remove:
        ec2Client = boto3.client('ec2',    
        aws_access_key_id=env.str('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=env.str('AWS_SECRET_ACCESS_KEY'),
        region_name='us-east-1')
        ec2Resource = boto3.resource('ec2')
        ec2 = boto3.resource('ec2')
        instance = ec2.Instance(remove)
        print(instance.terminate())


def start_instance_aws(ami_id, instance_type, tag):
    ec2Client = boto3.client('ec2',    
    aws_access_key_id=env.str('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=env.str('AWS_SECRET_ACCESS_KEY'),
    region_name='us-east-1')
    ec2Resource = boto3.resource('ec2')
    ec2 = boto3.resource('ec2')
    user_data='''#!/bin/bash
    cd /home/ubuntu
    hostname=$(ssh -i osparc-staging.pem -oStrictHostKeyChecking=no ubuntu@staging.osparc.io "hostname" 2>&1)
    token=$(ssh -i osparc-staging.pem -oStrictHostKeyChecking=no ubuntu@staging.osparc.io "docker swarm join-token -q worker" 2>&1)
    host=$(ssh -i osparc-staging.pem -oStrictHostKeyChecking=no ubuntu@staging.osparc.io "docker swarm join-token worker" 2>&1)
    docker swarm join --token ${token} ${host##* }
    label=$(ssh -i osparc-staging.pem -oStrictHostKeyChecking=no ubuntu@staging.osparc.io "docker node ls | grep $(hostname)")
    label="$(cut -d' ' -f1 <<<"$label")"
    ssh -i osparc-staging.pem -oStrictHostKeyChecking=no ubuntu@staging.osparc.io "docker node update --label-add sidecar=true $label"
    service_sidecar_id=$(ssh -i osparc-staging.pem -oStrictHostKeyChecking=no ubuntu@staging.osparc.io "docker service ls | grep sidecar")
    service_sidecar_id="$(cut -d' ' -f1 <<<"$service_sidecar_id")"
    replicas_number=$(ssh -i osparc-staging.pem -oStrictHostKeyChecking=no ubuntu@staging.osparc.io "docker service inspect $service_sidecar_id | jq '.[0].Spec.Mode.Replicated.Replicas'")
    new_replicas_number=`expr $replicas_number + 16`
    echo $new_replicas_number
    ssh -i osparc-staging.pem -oStrictHostKeyChecking=no ubuntu@staging.osparc.io "docker service update --replicas $new_replicas_number $service_sidecar_id" 
    '''
    # Create the instance
    instanceDict = ec2.create_instances(
        ImageId = ami_id,
        KeyName = "osparc-staging",
        InstanceType = instance_type,
        SecurityGroupIds = ["sg-076928a01feb651e5"],
        MinCount = 1,
        MaxCount = 1,
        SubnetId='subnet-0fbe53a929ce1bc2c',
        TagSpecifications=[ { 'ResourceType':'instance', 'Tags': [{'Key': 'Name','Value': tag}]}],
        UserData=user_data)
    instanceDict = instanceDict[0]
    print("Instance state: %s" % instanceDict.state)
    print("Public dns: %s" % instanceDict.public_dns_name)
    print("Instance id: %s" % instanceDict.id)


def start_instance_dalco(ami_id, instance_type, tag):
    print("ok")
    ec2Client = boto3.client('ec2',    
    aws_access_key_id=env.str('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=env.str('AWS_SECRET_ACCESS_KEY'),
    region_name='us-east-1')

    ec2Resource = boto3.resource('ec2', region_name='us-east-1')
    ec2 = boto3.resource('ec2', region_name='us-east-1')
    user_data='''#!/bin/bash
    cd /home/ubuntu
    '''

    # Create the instance
    instanceDict = ec2.create_instances(
        ImageId = ami_id,
        KeyName = "osparc-staging",
        InstanceType = instance_type,
        SecurityGroupIds = ["sg-076928a01feb651e5"],
        MinCount = 1,
        MaxCount = 1,
        SubnetId='subnet-0fbe53a929ce1bc2c',
        TagSpecifications=[ { 'ResourceType':'instance', 'Tags': [{'Key': 'Name','Value': tag}]}],
        UserData=user_data)
    instanceDict = instanceDict[0]
    print("Instance state: %s" % instanceDict.state)
    print("Public dns: %s" % instanceDict.public_dns_name)
    print("Instance id: %s" % instanceDict.id)

if __name__ == '__main__':
    cli()