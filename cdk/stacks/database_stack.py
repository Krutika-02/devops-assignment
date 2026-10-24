from aws_cdk import (
    Stack,
    aws_elasticache as elasticache,
    aws_ec2 as ec2,
)
from constructs import Construct


class DatabaseStack(Stack):
    """
    Provisions Managed AWS ElastiCache for Redis:
    - Located securely inside isolated private database subnets
    - Encrypted at rest
    - Parameter group configured for Celery task queuing
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        redis_security_group: ec2.ISecurityGroup,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. ElastiCache Subnet Group (Isolated private subnets)
        isolated_subnet_ids = [
            subnet.subnet_id for subnet in vpc.isolated_subnets
        ]

        self.subnet_group = elasticache.CfnSubnetGroup(
            self,
            "RedisSubnetGroup",
            description="Subnet group for Redis Celery broker in isolated subnets",
            subnet_ids=isolated_subnet_ids,
            cache_subnet_group_name="devops-redis-subnet-group",
        )

        # 2. ElastiCache Parameter Group
        self.param_group = elasticache.CfnParameterGroup(
            self,
            "RedisParameterGroup",
            cache_parameter_group_family="redis7",
            description="Optimized parameter group for Celery message broker",
            properties={
                "maxmemory-policy": "allkeys-lru",
            },
        )

        # 3. Managed ElastiCache Redis Cluster (Replication Group)
        self.redis_cluster = elasticache.CfnReplicationGroup(
            self,
            "RedisReplicationGroup",
            replication_group_description="Managed Redis broker and result backend for Celery",
            engine="redis",
            engine_version="7.0",
            cache_node_type="cache.t4g.micro",
            num_cache_clusters=1,
            automatic_failover_enabled=False,
            cache_subnet_group_name=self.subnet_group.cache_subnet_group_name,
            cache_parameter_group_name=self.param_group.ref,
            security_group_ids=[redis_security_group.security_group_id],
            at_rest_encryption_enabled=True,
            transit_encryption_enabled=False,
        )
        self.redis_cluster.add_dependency(self.subnet_group)

    @property
    def redis_endpoint(self) -> str:
        return self.redis_cluster.attr_primary_end_point_address
