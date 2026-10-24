# Cloud Architecture & Infrastructure Design

This document details the production cloud architecture for the containerized Notification Engine deployed on AWS using AWS CDK (Python).

---

## 1. High-Level Architecture Diagram

```mermaid
flowchart TD
    User([🌐 End User / Browser])
    
    subgraph AWS_Cloud ["AWS Cloud (Region: us-east-1)"]
        subgraph Public_Subnets ["Public Subnets (AZ-a & AZ-b)"]
            ALB["Application Load Balancer (ALB)\nPort 80 / 443"]
            NAT["NAT Gateway (Outbound Internet)"]
        end

        subgraph Private_App_Subnets ["Private App Subnets (AZ-a & AZ-b)"]
            subgraph ECS_Cluster ["AWS ECS Fargate Cluster"]
                BackendService["FastAPI Backend Service\n(Task Count: 2, Port: 8000)"]
                WorkerService["Celery Worker Service\n(Task Count: 2, Background Process)"]
            end
        end

        subgraph Isolated_DB_Subnets ["Isolated Database Subnets"]
            ElastiCache["AWS ElastiCache for Redis 7.0\n(Broker & Result Backend, Port: 6379)"]
        end

        subgraph Management_Observability ["Managed Services & Observability"]
            ECR["Amazon ECR\n(Backend & Worker Images)"]
            CloudWatchLogs["Amazon CloudWatch Logs\n(/ecs/backend & /ecs/worker)"]
            CloudWatchMetrics["CloudWatch Metrics & Alarms\n(CPU, Memory, 5XX Errors)"]
            CW_Dashboard["CloudWatch Dashboard\n(Real-Time Visibility)"]
        end
    end

    %% Network & Request Flow
    User -->|HTTP Requests| ALB
    ALB -->|Path: /notify* & /task_status/*| BackendService
    ALB -->|Path: / | User

    BackendService -->|Enqueue Task| ElastiCache
    WorkerService -->|Consume Task & Write Result| ElastiCache

    BackendService -->|Push App Logs| CloudWatchLogs
    WorkerService -->|Push Worker Logs| CloudWatchLogs

    ECS_Cluster -->|Metrics & Alarms| CloudWatchMetrics
    CloudWatchMetrics --> CW_Dashboard

    Private_App_Subnets -->|Image Pull via NAT| ECR
    NAT -->|Outbound HTTPS| AWS_Cloud
```

---

## 2. Component Breakdown

| Layer | Service | Purpose | Managed Service Justification |
|-------|---------|---------|-------------------------------|
| **Ingress** | AWS Application Load Balancer (ALB) | SSL termination, health checking, traffic distribution across AZs | Zero server maintenance, automated scaling, seamless integration with ECS IP targets. |
| **Compute** | AWS ECS on AWS Fargate | Runs FastAPI backend and Celery workers | Serverless container orchestration. Eliminates EC2 patching, OS management, and capacity planning. |
| **Message Broker** | AWS ElastiCache for Redis 7.0 | In-memory message broker & task status result backend | Fully managed, automated failure detection, multi-AZ replication, in-transit & at-rest encryption. |
| **Registry** | Amazon Elastic Container Registry (ECR) | Stores versioned Docker images | Built-in vulnerability scanning on push, lifecycle policies to prune stale images. |
| **Observability** | Amazon CloudWatch | Centralized logging, alarms, and dashboards | Native log forwarding via `awslogs` driver, real-time alerting on container failure or CPU spikes. |
| **Network** | Amazon VPC | Multi-AZ network isolation across public, private, and database subnets | Defense-in-depth isolation; Redis is physically unreachable from the public internet. |

---

## 3. Request & Task Execution Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Client as Web Frontend / Client
    participant ALB as Application Load Balancer
    participant API as FastAPI Backend (ECS Fargate)
    participant Redis as ElastiCache Redis
    participant Worker as Celery Worker (ECS Fargate)
    participant CW as CloudWatch Logs

    Client->>ALB: POST /notify/?email=user@example.com
    ALB->>API: Forward request to port 8000
    API->>Redis: Enqueue Celery Task (task_id: uuid)
    API->>CW: Log task enqueued
    API-->>Client: 200 OK {"task_id": "uuid", "status": "queued"}

    loop Every 1.5s
        Client->>ALB: GET /task_status/{task_id}
        ALB->>API: Forward status query
        API->>Redis: Query AsyncResult(task_id, app=celery)
        Redis-->>API: Return state (STARTED / PENDING)
        API-->>Client: {"status": "in progress"}
    end

    Redis->>Worker: Worker dequeues task
    Note over Worker: Simulates task execution (10s)
    Worker->>Redis: Store task completion state & result
    Worker->>CW: Log task finished successfully

    Client->>ALB: GET /task_status/{task_id}
    ALB->>API: Forward status query
    API->>Redis: Query AsyncResult(task_id, app=celery)
    Redis-->>API: Return state (COMPLETED + result payload)
    API-->>Client: {"status": "completed", "result": "Task completed: ..."}
```

---

## 4. Security & Network Boundaries

1. **Public Internet -> ALB**: Only Port 80/443 open to `0.0.0.0/0`.
2. **ALB -> ECS Backend**: Port 8000 strictly restricted to incoming traffic from the ALB Security Group.
3. **ECS Backend / Worker -> Redis**: Port 6379 strictly restricted to the ECS Security Group. Direct access from the internet or other subnets is blocked at the VPC routing and Security Group layers.
4. **Container Security**: All containers run with non-root user `appuser` (UID 1000).
