# Local Developer Instructions

This guide provides step-by-step instructions to run, verify, and debug the containerized application stack locally using Docker Compose.

---

## 📋 Prerequisites

Before starting, ensure the following are installed:
- [Docker](https://docs.docker.com/get-docker/) (v20.10+ recommended)
- [Docker Compose](https://docs.docker.com/compose/) (v2.0+ recommended)
- `curl` (or Postman / HTTP client)
- Web browser

---

## 🚀 1. Build and Run the Stack

### Step 1: Clone the repository and navigate into the directory
```bash
git clone https://github.com/Krutika-02/devops-assignment.git
cd devops-assignment
```

### Step 2: (Optional) Review Environment Variables
Copy `.env.example` if you wish to adjust ports or log filenames:
```bash
cp .env.example .env
```
*(Default settings work immediately out-of-the-box without editing!)*

### Step 3: Build All Container Images
Build the backend, worker, and frontend images from scratch:
```bash
docker compose build
```

### Step 4: Start the Full Application Stack
Start all services in detached background mode:
```bash
docker compose up -d
```

### Step 5: Verify Running Containers
Check that all 4 containers are healthy and running:
```bash
docker compose ps
```

You should see:
| Name | Image | Status | Ports |
|------|-------|--------|-------|
| `devops-redis` | `redis:7-alpine` | Up (healthy) | `0.0.0.0:6379->6379/tcp` |
| `devops-backend` | `devops-assignment-backend` | Up (healthy) | `0.0.0.0:8000->8000/tcp` |
| `devops-worker` | `devops-assignment-worker` | Up | (internal network) |
| `devops-frontend` | `devops-assignment-frontend` | Up (healthy) | `0.0.0.0:3000->80/tcp` |

---

## 🌐 2. Access the Application

- **Frontend User Interface:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Backend Root:** [http://localhost:8000/](http://localhost:8000/)
- **FastAPI Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **FastAPI Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 🔍 3. View Logs and Debug Issues

### View all logs in real-time
```bash
docker compose logs -f
```

### Follow logs for a specific service
- **FastAPI Backend logs:**
  ```bash
  docker compose logs -f backend
  ```
- **Celery Worker logs (shows background task consumption):**
  ```bash
  docker compose logs -f worker
  ```
- **Redis logs:**
  ```bash
  docker compose logs -f redis
  ```
- **Frontend Nginx logs:**
  ```bash
  docker compose logs -f frontend
  ```

### Inspect Redis Messages & Queues
To verify that tasks are landing in Redis:
```bash
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli KEYS "*"
```

### Check Worker Log File Inside Container
The worker persists completed tasks to a log file:
```bash
docker compose exec worker cat /app/logs/log_celery.txt
```

---

## 🧪 4. End-to-End API Testing via CLI

You can test the entire workflow directly using `curl`:

### 1. Trigger a background notification task
```bash
curl -X POST "http://localhost:8000/notify/?email=developer@superclaims.ai"
```
**Sample Response:**
```json
{
  "message": "Email will be sent to developer@superclaims.ai",
  "task_id": "78c94628-98e3-4613-8991-62fc92c423aa",
  "status": "queued"
}
```

### 2. Poll the task status immediately (In Progress)
```bash
curl "http://localhost:8000/task_status/78c94628-98e3-4613-8991-62fc92c423aa"
```
**Sample Response:**
```json
{
  "task_id": "78c94628-98e3-4613-8991-62fc92c423aa",
  "status": "in progress"
}
```

### 3. Check again after 10 seconds (Completed)
```bash
curl "http://localhost:8000/task_status/78c94628-98e3-4613-8991-62fc92c423aa"
```
**Sample Response:**
```json
{
  "task_id": "78c94628-98e3-4613-8991-62fc92c423aa",
  "status": "completed",
  "result": "Task completed: Notification sent to developer@superclaims.ai"
}
```

---

## 🛑 5. Stopping and Cleaning Up

### Stop the containers (preserve data volumes):
```bash
docker compose down
```

### Stop and remove all containers, networks, and persistent volumes:
```bash
docker compose down -v
```

---

## 🛠️ 6. Running Local Unit Tests (Without Docker)

If you have a local Python 3.11+ environment:
```bash
# Install dependencies
pip install -r requirements.txt

# Run full pytest suite
pytest tests -v
```
