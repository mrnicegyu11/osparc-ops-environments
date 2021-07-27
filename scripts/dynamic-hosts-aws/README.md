# Purpose

This python script launch an EC2 instance on the AWS OSPARC stack and makes it join the swarm automatically.

# Installation

* Create a virtualenvironment with python 3.X and activate it
```console
python3 -m venv env
source env/bin/activate
```
* Install the dependancies
```console 
pip install -r requirements.yxy
```

* Copy template.env to .env and fill the aws credentials
* Run the script
```console
python dynamic-host-aws.py --help
```