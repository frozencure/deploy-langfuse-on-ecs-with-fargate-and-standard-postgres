#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab

import json

import aws_cdk as cdk

from aws_cdk import (
  Stack,
  aws_ec2,
  aws_rds,
  aws_secretsmanager
)

from constructs import Construct


class StandardPostgresqlStack(Stack):

  def __init__(self, scope: Construct, construct_id: str, vpc, **kwargs) -> None:
    super().__init__(scope, construct_id, **kwargs)

    db_instance_name = self.node.try_get_context('db_instance_name') or 'langfuse-db-instance'

    sg_postgresql_client = aws_ec2.SecurityGroup(self, 'PostgreSQLClientSG',
      vpc=vpc,
      allow_all_outbound=True,
      description='security group for postgresql client',
      security_group_name=f'{db_instance_name}-postgresql-client-sg'
    )
    cdk.Tags.of(sg_postgresql_client).add('Name', 'postgresql-client-sg')

    sg_postgresql_server = aws_ec2.SecurityGroup(self, 'PostgreSQLServerSG',
      vpc=vpc,
      allow_all_outbound=True,
      description='security group for postgresql',
      security_group_name=f'{db_instance_name}-postgresql-server-sg'
    )
    sg_postgresql_server.add_ingress_rule(peer=sg_postgresql_client, connection=aws_ec2.Port.tcp(5432),
      description='postgresql-client-sg')
    cdk.Tags.of(sg_postgresql_server).add('Name', 'postgresql-server-sg')

    rds_subnet_group = aws_rds.SubnetGroup(self, 'PostgreSQLSubnetGroup',
      description='subnet group for postgresql',
      subnet_group_name=f'standard-postgresql-{self.stack_name}',
      vpc_subnets=aws_ec2.SubnetSelection(subnet_type=aws_ec2.SubnetType.PRIVATE_WITH_EGRESS),
      vpc=vpc
    )

    db_secret = aws_secretsmanager.Secret(self, 'DatabaseSecret',
      generate_secret_string=aws_secretsmanager.SecretStringGenerator(
        secret_string_template=json.dumps({"username": "postgres"}),
        generate_string_key="password",
        exclude_punctuation=True,
        password_length=8
      )
    )
    rds_credentials = aws_rds.Credentials.from_secret(db_secret)

    rds_engine = aws_rds.DatabaseInstanceEngine.postgres(version=aws_rds.PostgresEngineVersion.VER_15_4)

    db_instance = aws_rds.DatabaseInstance(self, 'DatabaseInstance',
      engine=rds_engine,
      credentials=rds_credentials,
      instance_type=aws_ec2.InstanceType.of(aws_ec2.InstanceClass.BURSTABLE4_GRAVITON, aws_ec2.InstanceSize.SMALL),
      vpc=vpc,
      vpc_subnets=aws_ec2.SubnetSelection(subnet_type=aws_ec2.SubnetType.PRIVATE_WITH_EGRESS),
      security_groups=[sg_postgresql_server],
      subnet_group=rds_subnet_group,
      allocated_storage=20,
      backup_retention=cdk.Duration.days(3),
      delete_automated_backups=True,
      deletion_protection=False,
      publicly_accessible=False,
      storage_type=aws_rds.StorageType.GP3,
      max_allocated_storage=100,
    )

    self.sg_rds_client = sg_postgresql_client
    self.database_secret = db_secret
    self.database = db_instance

    cdk.CfnOutput(self, 'DBInstanceEndpoint',
      value=db_instance.db_instance_endpoint_address,
      export_name=f'{self.stack_name}-DBInstanceEndpoint')
    cdk.CfnOutput(self, 'RDSClientSecurityGroupId',
      value=sg_postgresql_client.security_group_id,
      export_name=f'{self.stack_name}-RDSClientSecurityGroupId')
    cdk.CfnOutput(self, 'DBSecretName',
      value=db_secret.secret_name,
      export_name=f'{self.stack_name}-DBSecretName')