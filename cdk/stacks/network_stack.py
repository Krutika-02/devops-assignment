from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct


class NetworkStack(Stack):
    """
    Provisions network infrastructure:
    - Highly available VPC across 2 Availability Zones
    - Public subnets with Internet Gateway
    - Isolated Private subnets with NAT Gateway for outbound traffic
    - Principle of Least Privilege Security Groups
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Multi-AZ VPC
        self.vpc = ec2.Vpc(
            self,
            "AppVPC",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="IsolatedDatabase",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # 2. ALB Security Group (Public HTTP)
        self.alb_security_group = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            vpc=self.vpc,
            description="Allows inbound HTTP from internet to Application Load Balancer",
            allow_all_outbound=True,
        )
        self.alb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP from anywhere",
        )

        # 3. ECS Task Security Group
        self.ecs_security_group = ec2.SecurityGroup(
            self,
            "EcsSecurityGroup",
            vpc=self.vpc,
            description="Allows ingress from ALB to ECS containers",
            allow_all_outbound=True,
        )
        self.ecs_security_group.add_ingress_rule(
            peer=self.alb_security_group,
            connection=ec2.Port.tcp(8000),
            description="Allow inbound traffic from ALB only",
        )

        # 4. Redis Security Group (Strictly restricted to ECS tasks)
        self.redis_security_group = ec2.SecurityGroup(
            self,
            "RedisSecurityGroup",
            vpc=self.vpc,
            description="Strictly allows inbound Redis port 6379 from ECS tasks only",
            allow_all_outbound=False,
        )
        self.redis_security_group.add_ingress_rule(
            peer=self.ecs_security_group,
            connection=ec2.Port.tcp(6379),
            description="Allow Redis traffic strictly from ECS tasks",
        )
