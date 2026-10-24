#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.network_stack import NetworkStack
from stacks.database_stack import DatabaseStack
from stacks.ecs_stack import EcsStack
from stacks.monitoring_stack import MonitoringStack

app = cdk.App()

# Target AWS Environment
env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT", os.getenv("AWS_ACCOUNT_ID")),
    region=os.getenv("CDK_DEFAULT_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
)

# 1. Network Stack (VPC, Subnets, Security Groups)
network_stack = NetworkStack(app, "DevOpsNetworkStack", env=env)

# 2. Database Stack (AWS Managed ElastiCache for Redis)
database_stack = DatabaseStack(
    app,
    "DevOpsDatabaseStack",
    vpc=network_stack.vpc,
    redis_security_group=network_stack.redis_security_group,
    env=env,
)
database_stack.add_dependency(network_stack)

# 3. ECS Compute & Orchestration Stack (Fargate, ALB, ECR)
ecs_stack = EcsStack(
    app,
    "DevOpsEcsStack",
    vpc=network_stack.vpc,
    alb_security_group=network_stack.alb_security_group,
    ecs_security_group=network_stack.ecs_security_group,
    redis_endpoint=database_stack.redis_endpoint,
    env=env,
)
ecs_stack.add_dependency(database_stack)

# 4. Observability Stack (CloudWatch Alarms & Dashboards)
monitoring_stack = MonitoringStack(
    app,
    "DevOpsMonitoringStack",
    cluster=ecs_stack.cluster,
    backend_service=ecs_stack.backend_service,
    worker_service=ecs_stack.worker_service,
    alb=ecs_stack.alb,
    env=env,
)
monitoring_stack.add_dependency(ecs_stack)

app.synth()
