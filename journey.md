# Engineering Journey: Containerization, IaC & Cloud Automation

This document records the architectural analysis, design decisions, trade-offs, and challenges encountered while containerizing and automating the deployment of the Notification & Task Status application.

---

## 1. Initial Assessment & Code Audit

Upon receiving the initial repository, we identified the four core components:
1. **FastAPI Backend (`backend/main.py`)**: An asynchronous REST API responsible for ingesting notification requests and returning task statuses.
2. **Celery Worker (`backend/worker.py`)**: A distributed worker that consumes notification events from a queue, processes them asynchronously (simulating a 10-second workload), and appends to a log file.
3. **Redis Broker & Result Store**: The message broker orchestrating message exchange and task state persistence.
4. **Single-Page Frontend (`frontend/index.html`)**: An HTML client to trigger tasks and poll for status.

### Hardcoded Values Identified:
- **Redis Connection Strings**: In `backend/worker.py`, Celery was hardcoded to `redis://localhost:6379/0`. Inside Docker or AWS VPC, containers reside on dedicated network interfaces or private subnets, making `localhost` non-functional.
- **Log File Destination**: Hardcoded to `log_celery.txt` in the process working directory, which does not survive container restarts or conform to 12-factor application logging.
- **Task Duration**: Hardcoded 10-second sleep (`time.sleep(10)`), which slowed down integration and unit testing.
- **Frontend Target Origin**: Hardcoded to `http://localhost:8000`, preventing the frontend from communicating with cloud-hosted backends behind Application Load Balancers.
- **CORS Allowed Origins**: Hardcoded to `["*"]` without environment variable override capability.

---

## 2. Key Architectural Decisions

### Decision 1: Parameterization via 12-Factor App Principles
We refactored `backend/worker.py` and `backend/main.py` to read all environmental configurations via `os.getenv` with sensible fallbacks:
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `TASK_DURATION_SECONDS` (allowing 0s during automated unit testing)
- `CELERY_LOG_FILE` (pointing to a persistent volume `/app/logs/log_celery.txt`)
- `CORS_ORIGINS`, `HOST`, `PORT`

### Decision 2: Celery AsyncResult App Binding Fix
**Bug Identified:** In the original `backend/main.py`:
```python
task_result = AsyncResult(task_id)
```
Calling `AsyncResult` without binding it to the configured Celery instance causes Celery to fall back to `current_app`, which lacks connection to the Redis result backend in multi-process setups.
**Resolution:** We updated the status query to explicitly pass the configured `celery` application:
```python
task_result = AsyncResult(task_id, app=celery)
```
This guaranteed that task status queries reliably read execution results from Redis across different containers and processes.

### Decision 3: Unified Multi-Purpose Dockerfile with Non-Root Security
Rather than maintaining divergent Dockerfiles for the FastAPI backend and the Celery worker, we designed a unified production Dockerfile:
- Leverages `python:3.11-slim` for minimal image size and reduced attack surface.
- Implements a dedicated non-root user (`appuser`, UID 1000) for security hardening.
- Implements container-level `HEALTHCHECK` using `curl` against `/health`.
- Allows overriding the default entrypoint in `docker-compose.yml` (`uvicorn` for the backend, `celery` for the worker).

### Decision 4: Frontend Nginx Container & Reverse Proxy
To avoid CORS complexities and deliver a cloud-native single-page experience:
- Packaged `frontend/index.html` inside an `nginx:1.25-alpine` container.
- Configured Nginx to reverse-proxy `/notify` and `/task_status` requests directly to `http://backend:8000`.
- Enhanced the UI with real-time status badges (`QUEUED` -> `IN PROGRESS` -> `COMPLETED` / `FAILED`), live progress bar, elapsed timer, and auto-detecting backend endpoint toggle.

### Decision 5: Infrastructure as Code (AWS CDK in Python)
To adhere to modern cloud engineering practices, we authored complete Infrastructure as Code in **AWS CDK (Python)**:
- **Networking**: Multi-AZ VPC across 2 Availability Zones with Public Subnets, Private Subnets with NAT Gateway, and Isolated Database Subnets.
- **Container Orchestration**: **AWS ECS Fargate** (serverless containers, no EC2 instances to manage or patch).
- **Managed Message Broker**: **AWS ElastiCache for Redis 7.0** deployed in isolated subnets with encryption at rest and security groups strictly locked to ECS tasks.
- **Routing**: **AWS Application Load Balancer (ALB)** with path-based routing (`/notify*`, `/task_status/*` to backend target group; `/` to frontend).
- **Observability**: **AWS CloudWatch** Log Groups (14-day retention), CPU/Memory metric alarms, and an operational dashboard.

### Decision 6: Automated CI/CD Pipeline (GitHub Actions)
Constructed a 4-stage GitHub Actions pipeline (`.github/workflows/ci-cd.yml`):
1. **Automated Unit & Integration Testing**: Spins up an ephemeral Redis service container and runs pytest.
2. **Container Build Verification**: Builds backend and frontend Docker images, runs a smoke test with Docker Compose.
3. **IaC Synthesis & Validation**: Validates AWS CDK constructs and runs `cdk synth`.
4. **Zero-Downtime Deployment**: Pushes images to Amazon ECR and deploys updated task definitions to ECS Fargate upon merge to `main`.

---

## 3. Challenges Faced & Solutions

| Challenge | Impact | Solution |
|-----------|--------|----------|
| **Redis connection inside Docker Compose** | Backend and worker could not connect to `localhost:6379` | Configured Docker Compose service discovery via bridge network: `REDIS_URL=redis://redis:6379/0` with healthcheck dependencies. |
| **Worker startup race condition** | Worker crashing if started before Redis was ready | Added `redis-cli ping` healthcheck to Redis service and `depends_on: { redis: { condition: service_healthy } }`. |
| **Testing Celery bound tasks** | Calling task function directly failed due to `@celery.task(bind=True)` argument expectations | Invoked `task.run(message)` in unit tests, allowing clean unit verification of file writing without requiring live Redis brokers. |
| **Non-root file permissions in container** | Worker unable to write to `/app/logs` | Explicitly created `/app/logs` directory and ran `chown -R appuser:appuser /app` in the Dockerfile prior to switching to `USER appuser`. |

---

## 4. Conclusion & Operational Impact

The resulting system transforms a localized Python prototype into a fully containerized, cloud-deployable, automated production architecture:
- **Reproducible Locally:** A single `docker compose up -d` boots the entire four-tier stack.
- **Cloud-Native:** Fully decoupled compute (ECS Fargate) and state (AWS ElastiCache Redis).
- **Automated:** Zero-touch CI/CD pipeline enforcing tests, security scans, and continuous deployment.
