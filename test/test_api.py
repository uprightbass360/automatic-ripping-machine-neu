"""Tests for the REST API layer (arm/api/v1/)."""
import unittest.mock

import pytest


@pytest.fixture
def client(app_context):
    """Flask test client."""
    app, db = app_context
    app.config['LOGIN_DISABLED'] = True
    with app.test_client() as client:
        yield client


class TestApiJobsList:
    """Test GET /api/v1/jobs endpoint."""

    def test_list_jobs_returns_json(self, client):
        response = client.get('/api/v1/jobs')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)

    def test_list_jobs_with_status_filter(self, client):
        response = client.get('/api/v1/jobs?status=success')
        assert response.status_code == 200

    def test_list_jobs_fail_status(self, client):
        response = client.get('/api/v1/jobs?status=fail')
        assert response.status_code == 200

    def test_list_jobs_search(self, client):
        response = client.get('/api/v1/jobs?q=serial')
        assert response.status_code == 200


class TestApiJobDelete:
    """Test DELETE /api/v1/jobs/<id> endpoint."""

    def test_delete_nonexistent_job(self, client):
        response = client.delete('/api/v1/jobs/99999')
        assert response.status_code in (200, 404)


class TestApiJobAbandon:
    """Test POST /api/v1/jobs/<id>/abandon endpoint."""

    def test_abandon_nonexistent_raises(self, client):
        """Upstream json_api.abandon_job doesn't handle missing jobs gracefully."""
        # json_api.abandon_job tries to set attrs on None (Job.query.get returns None)
        with pytest.raises(AttributeError):
            client.post('/api/v1/jobs/99999/abandon')

    def test_abandon_with_mock(self, client):
        with unittest.mock.patch('arm.api.v1.jobs.json_api') as mock_api:
            mock_api.abandon_job.return_value = {"success": True}
            response = client.post('/api/v1/jobs/1/abandon')
            assert response.status_code == 200


class TestApiJobConfig:
    """Test PATCH /api/v1/jobs/<id>/config endpoint."""

    def test_change_config_nonexistent(self, client):
        response = client.patch(
            '/api/v1/jobs/99999/config',
            json={"RIPMETHOD": "mkv"},
            content_type='application/json',
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False

    def test_change_config_empty_body(self, client, sample_job, app_context):
        response = client.patch(
            f'/api/v1/jobs/{sample_job.job_id}/config',
            json={},
            content_type='application/json',
        )
        assert response.status_code == 400

    def test_change_config_invalid_ripmethod(self, client, sample_job, app_context):
        response = client.patch(
            f'/api/v1/jobs/{sample_job.job_id}/config',
            json={"RIPMETHOD": "invalid"},
            content_type='application/json',
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "RIPMETHOD" in data["error"]

    def test_change_config_success(self, client, sample_job, app_context):
        response = client.patch(
            f'/api/v1/jobs/{sample_job.job_id}/config',
            json={"RIPMETHOD": "backup", "MAINFEATURE": True, "MINLENGTH": 600},
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["job_id"] == sample_job.job_id


class TestApiJobFixPermissions:
    """Test POST /api/v1/jobs/<id>/fix-permissions endpoint."""

    def test_fix_permissions_with_mock(self, client):
        with unittest.mock.patch('arm.api.v1.jobs.ui_utils') as mock_utils:
            mock_utils.fix_permissions.return_value = {"success": True}
            response = client.post('/api/v1/jobs/1/fix-permissions')
            assert response.status_code == 200


class TestApiJobSend:
    """Test POST /api/v1/jobs/<id>/send endpoint."""

    def test_send_with_mock(self, client):
        with unittest.mock.patch('arm.api.v1.jobs.ui_utils') as mock_utils:
            mock_utils.send_to_remote_db.return_value = {"success": True}
            response = client.post('/api/v1/jobs/1/send')
            assert response.status_code == 200


class TestApiJobLog:
    """Test GET /api/v1/jobs/<id>/log endpoint."""

    def test_get_log_nonexistent_job(self, client):
        response = client.get('/api/v1/jobs/99999/log')
        assert response.status_code in (200, 404)


class TestApiNotifications:
    """Test PATCH /api/v1/notifications/<id> endpoint."""

    def test_read_notification(self, client):
        response = client.patch('/api/v1/notifications/99999')
        assert response.status_code in (200, 404)


class TestApiNotifyTimeout:
    """Test GET /api/v1/settings/notify-timeout endpoint."""

    def test_get_notify_timeout(self, client):
        response = client.get('/api/v1/settings/notify-timeout')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None


class TestApiSystemRestart:
    """Test POST /api/v1/system/restart endpoint."""

    def test_restart_returns_response(self, client):
        with unittest.mock.patch('arm.api.v1.system.json_api') as mock_api:
            mock_api.restart_ui.return_value = {"success": True}
            response = client.post('/api/v1/system/restart')
            assert response.status_code == 200
