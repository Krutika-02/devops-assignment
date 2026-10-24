import os
import time
import logging
from celery import Celery

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("worker")

# Environment variables with sensible defaults
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_LOG_FILE = os.getenv("CELERY_LOG_FILE", "log_celery.txt")
TASK_DURATION_SECONDS = int(os.getenv("TASK_DURATION_SECONDS", "10"))

# Configure Celery
celery = Celery(
    "worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Celery configuration optimizations
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,  # Expire results after 1 hour
)


@celery.task(bind=True, name="worker.write_log_celery")
def write_log_celery(self, message: str):
    """
    Background Celery task that simulates processing, logs to disk, and returns a result.
    """
    logger.info(f"[Task {self.request.id}] Started processing: {message}")
    
    # Simulate processing time
    time.sleep(TASK_DURATION_SECONDS)
    
    # Ensure log directory exists if a path is provided
    log_dir = os.path.dirname(CELERY_LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    try:
        with open(CELERY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception as e:
        logger.error(f"[Task {self.request.id}] Failed to write log file: {e}")

    result_msg = f"Task completed: {message}"
    logger.info(f"[Task {self.request.id}] Finished successfully: {result_msg}")
    return result_msg
