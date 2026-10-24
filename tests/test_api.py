import sys
import os
from unittest.mock import patch, MagicMock

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns 200 OK and expected API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "endpoints" in data


def test_health_endpoint():
    """Verify health endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["service"] == "backend"


def test_health_post_endpoint():
    """Verify health endpoint supports POST as requested by specification."""
    response = client.post("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"


@patch("main.write_log_celery.delay")
def test_notify_endpoint(mock_delay):
    """Verify notify endpoint enqueues a Celery task."""
    mock_task = MagicMock()
    mock_task.id = "test-task-uuid-12345"
    mock_delay.return_value = mock_task

    test_email = "test@example.com"
    response = client.post(f"/notify/?email={test_email}")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-task-uuid-12345"
    assert test_email in data["message"]
    mock_delay.assert_called_once_with(f"Notification sent to {test_email}")


@patch("main.AsyncResult")
def test_task_status_completed(mock_async_result):
    """Verify task status endpoint handles completed task state."""
    mock_result_instance = MagicMock()
    mock_result_instance.ready.return_value = True
    mock_result_instance.successful.return_value = True
    mock_result_instance.result = "Task completed: Notification sent to test@example.com"
    mock_async_result.return_value = mock_result_instance

    response = client.get("/task_status/test-task-uuid-12345")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["task_id"] == "test-task-uuid-12345"
    assert "Task completed" in data["result"]


@patch("main.AsyncResult")
def test_task_status_in_progress(mock_async_result):
    """Verify task status endpoint handles in-progress task state."""
    mock_result_instance = MagicMock()
    mock_result_instance.ready.return_value = False
    mock_result_instance.state = "STARTED"
    mock_async_result.return_value = mock_result_instance

    response = client.get("/task_status/test-task-uuid-12345")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in progress"
