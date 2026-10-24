from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
)
from constructs import Construct


class EcsStack(Stack):
    """
    Provisions container orchestration & compute:
    - ECR Repositories with automated image vulnerability scanning
    - AWS ECS Fargate Cluster with Container Insights
    - Backend FastAPI Service (auto-restarted, scaled, health-monitored)
    - Celery Worker Service (consumes background tasks from Redis)
    - Application Load Balancer routing public HTTP traffic to backend
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        alb_security_group: ec2.ISecurityGroup,
        ecs_security_group: ec2.ISecurityGroup,
        redis_endpoint: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. AWS ECR Repositories
        self.backend_repo = ecr.Repository(
            self,
            "BackendRepo",
            repository_name="devops-backend",
            image_scan_on_push=True,
        )
        self.backend_repo.add_lifecycle_rule(max_image_count=15)

        self.worker_repo = ecr.Repository(
            self,
            "WorkerRepo",
            repository_name="devops-worker",
            image_scan_on_push=True,
        )
        self.worker_repo.add_lifecycle_rule(max_image_count=15)

        # 2. CloudWatch Log Groups (14-day retention)
        backend_log_group = logs.LogGroup(
            self,
            "BackendLogGroup",
            log_group_name="/ecs/devops-backend",
            retention=logs.RetentionDays.TWO_WEEKS,
        )

        worker_log_group = logs.LogGroup(
            self,
            "WorkerLogGroup",
            log_group_name="/ecs/devops-worker",
            retention=logs.RetentionDays.TWO_WEEKS,
        )

        # 3. ECS Fargate Cluster
        self.cluster = ecs.Cluster(
            self,
            "EcsCluster",
            vpc=vpc,
            cluster_name="devops-app-cluster",
            container_insights=True,
        )

        # 4. IAM Roles
        task_execution_role = iam.Role(
            self,
            "EcsTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        task_role = iam.Role(
            self,
            "EcsTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Common Redis Environment Variables
        redis_url = f"redis://{redis_endpoint}:6379/0"
        common_env = {
            "REDIS_URL": redis_url,
            "CELERY_BROKER_URL": redis_url,
            "CELERY_RESULT_BACKEND": redis_url,
            "PORT": "8000",
            "CORS_ORIGINS": "*",
        }

        # 5. Backend Task Definition & Container
        backend_task_def = ecs.FargateTaskDefinition(
            self,
            "BackendTaskDef",
            cpu=256,
            memory_limit_mib=512,
            execution_role=task_execution_role,
            task_role=task_role,
        )

        backend_container = backend_task_def.add_container(
            "BackendContainer",
            image=ecs.ContainerImage.from_ecr_repository(self.backend_repo, "latest"),
            environment=common_env,
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="backend",
                log_group=backend_log_group,
            ),
        )
        backend_container.add_port_mappings(
            ecs.PortMapping(container_port=8000, host_port=8000)
        )

        # 6. Worker Task Definition & Container
        worker_task_def = ecs.FargateTaskDefinition(
            self,
            "WorkerTaskDef",
            cpu=256,
            memory_limit_mib=512,
            execution_role=task_execution_role,
            task_role=task_role,
        )

        worker_env = dict(common_env)
        worker_env["TASK_DURATION_SECONDS"] = "10"

        worker_task_def.add_container(
            "WorkerContainer",
            image=ecs.ContainerImage.from_ecr_repository(self.worker_repo, "latest"),
            command=["celery", "-A", "worker.celery", "worker", "--loglevel=info"],
            environment=worker_env,
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="worker",
                log_group=worker_log_group,
            ),
        )

        # 7. ECS Services
        self.backend_service = ecs.FargateService(
            self,
            "BackendService",
            cluster=self.cluster,
            task_definition=backend_task_def,
            desired_count=2,
            security_groups=[ecs_security_group],
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            assign_public_ip=False,
        )

        self.worker_service = ecs.FargateService(
            self,
            "WorkerService",
            cluster=self.cluster,
            task_definition=worker_task_def,
            desired_count=2,
            security_groups=[ecs_security_group],
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            assign_public_ip=False,
        )

        # 8. Application Load Balancer
        self.alb = elbv2.ApplicationLoadBalancer(
            self,
            "AppALB",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        listener = self.alb.add_listener(
            "HttpListener",
            port=80,
            open=True,
        )

        # Target Group for Backend
        self.target_group = listener.add_targets(
            "BackendTarget",
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[self.backend_service],
            health_check=elbv2.HealthCheck(
                path="/health",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
        )

        # Stack Outputs
        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=self.alb.load_balancer_dns_name,
            description="Public DNS URL of Application Load Balancer",
        )
        CfnOutput(
            self,
            "BackendECRRepo",
            value=self.backend_repo.repository_uri,
            description="ECR URI for Backend container",
        )
        CfnOutput(
            self,
            "WorkerECRRepo",
            value=self.worker_repo.repository_uri,
            description="ECR URI for Worker container",
        )
