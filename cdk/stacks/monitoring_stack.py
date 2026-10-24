from aws_cdk import (
    Stack,
    Duration,
    aws_cloudwatch as cloudwatch,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
)
from constructs import Construct


class MonitoringStack(Stack):
    """
    Provisions cloud-native observability:
    - CloudWatch Alarms for CPU / Memory saturation
    - CloudWatch Dashboard for end-to-end operational visibility
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cluster: ecs.ICluster,
        backend_service: ecs.IBaseService,
        worker_service: ecs.IBaseService,
        alb: elbv2.IApplicationLoadBalancer,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. CloudWatch Metric Alarms
        backend_cpu_metric = cloudwatch.Metric(
            namespace="AWS/ECS",
            metric_name="CPUUtilization",
            dimensions_map={
                "ClusterName": cluster.cluster_name,
                "ServiceName": backend_service.service_name,
            },
            period=Duration.minutes(1),
            statistic="Average",
        )

        cloudwatch.Alarm(
            self,
            "BackendCpuAlarm",
            metric=backend_cpu_metric,
            threshold=80,
            evaluation_periods=2,
            alarm_description="Alert when FastAPI Backend CPU exceeds 80% for 2 consecutive minutes",
        )

        worker_cpu_metric = cloudwatch.Metric(
            namespace="AWS/ECS",
            metric_name="CPUUtilization",
            dimensions_map={
                "ClusterName": cluster.cluster_name,
                "ServiceName": worker_service.service_name,
            },
            period=Duration.minutes(1),
            statistic="Average",
        )

        cloudwatch.Alarm(
            self,
            "WorkerCpuAlarm",
            metric=worker_cpu_metric,
            threshold=85,
            evaluation_periods=2,
            alarm_description="Alert when Celery Worker CPU exceeds 85% for 2 consecutive minutes",
        )

        # 2. CloudWatch Dashboard
        dashboard = cloudwatch.Dashboard(
            self,
            "DevOpsAppDashboard",
            dashboard_name="DevOps-Application-Overview",
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="ECS Cluster CPU & Memory Utilization",
                width=12,
                left=[backend_cpu_metric, worker_cpu_metric],
            ),
            cloudwatch.GraphWidget(
                title="ALB Request Count",
                width=12,
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/ApplicationELB",
                        metric_name="RequestCount",
                        dimensions_map={"LoadBalancer": alb.load_balancer_full_name},
                        period=Duration.minutes(1),
                        statistic="Sum",
                    )
                ],
            ),
        )
