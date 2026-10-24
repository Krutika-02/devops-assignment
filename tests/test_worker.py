import sys
import os
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import worker


def test_celery_task_execution():
    """Verify write_log_celery task executes, writes log file and returns result."""
    with tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8") as temp_log:
        temp_log_path = temp_log.name

    try:
        with patch.object(worker, "CELERY_LOG_FILE", temp_log_path), \
             patch.object(worker, "TASK_DURATION_SECONDS", 0):

            # Celery bound task: .run() executes the wrapped function
            result = worker.write_log_celery.run("Unit test log entry")

            assert "Task completed: Unit test log entry" in result

            with open(temp_log_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "Unit test log entry" in content
    finally:
        if os.path.exists(temp_log_path):
            os.remove(temp_log_path)
