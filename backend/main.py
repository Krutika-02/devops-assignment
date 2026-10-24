import os
import logging
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from celery.result import AsyncResult
from worker import celery, write_log_celery

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("backend")

app = FastAPI(
    title="Notification & Task Status API",
    description="FastAPI service integrated with Celery background worker and Redis",
    version="1.0.0"
)

# Configurable CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint welcoming API users and providing service status."""
    return {
        "service": "Notification & Task Status API",
        "status": "healthy",
        "endpoints": {
            "notify": "POST /notify/?email=...",
            "task_status": "GET /task_status/{task_id}",
            "health": "GET /health"
        }
    }


@app.api_route("/health", methods=["GET", "POST"])
@app.api_route("/health/", methods=["GET", "POST"])
async def health():
    """Health check endpoint used by Docker, Kubernetes, and Load Balancers."""
    redis_status = "unknown"
    try:
        # Ping broker connection through Celery app
        with celery.connection_for_read() as conn:
            conn.connect()
            redis_status = "connected"
    except Exception as e:
        logger.warning(f"Health check Redis ping warning: {e}")
        redis_status = f"warning: {str(e)}"

    return {
        "status": "OK",
        "redis": redis_status,
        "service": "backend"
    }


@app.post("/notify/")
@app.post("/notify")
async def notify_user(email: str = Query(..., description="Target email address to notify")):
    """Endpoint that enqueues the background notification task in Celery."""
    logger.info(f"Enqueueing notification for email: {email}")
    task = write_log_celery.delay(f"Notification sent to {email}")
    logger.info(f"Enqueued Celery task ID: {task.id}")
    return {
        "message": f"Email will be sent to {email}",
        "task_id": task.id,
        "status": "queued"
    }


@app.get("/task_status/{task_id}")
async def get_task_status(task_id: str):
    """
    Endpoint to check the status of a Celery task.
    Passes the Celery app instance to AsyncResult for accurate backend state resolution.
    """
    task_result = AsyncResult(task_id, app=celery)

    state = task_result.state
    logger.info(f"Checking task_id={task_id}, current state={state}")

    if task_result.ready():
        if task_result.successful():
            return {
                "task_id": task_id,
                "status": "completed",
                "result": task_result.result
            }
        else:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(task_result.result)
            }
    elif state == "STARTED":
        return {"task_id": task_id, "status": "in progress"}
    elif state == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    else:
        return {"task_id": task_id, "status": state.lower()}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=False)
