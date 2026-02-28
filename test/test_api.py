"""Tests for the REST API layer (arm/api/v1/)."""
import unittest.mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(app_context):
    """FastAPI test client."""
    from arm.app import app
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


class TestApiJobsList:
    """Test GET /api/v1/jobs endpoint."""

    def test_list_jobs_returns_json(self, client):
        response = client.get('/api/v1/jobs')
        assert response.status_code == 200
        data = response.json()
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
        """Upstream svc_jobs.abandon_job doesn't handle missing jobs gracefully."""
        # abandon_job tries to set attrs on None (Job.query.get returns None)
        with pytest.raises(AttributeError):
            client.post('/api/v1/jobs/99999/abandon')

    def test_abandon_with_mock(self, client):
        with unittest.mock.patch('arm.api.v1.jobs.svc_jobs') as mock_api:
            mock_api.abandon_job.return_value = {"success": True}
            response = client.post('/api/v1/jobs/1/abandon')
            assert response.status_code == 200


class TestApiJobPause:
    """Test POST /api/v1/jobs/<id>/pause endpoint."""

    def test_pause_nonexistent_job(self, client):
        response = client.post('/api/v1/jobs/99999/pause')
        assert response.status_code == 404
        assert response.json()["success"] is False

    def test_pause_job_not_waiting(self, client, sample_job, app_context):
        """Can only pause jobs in MANUAL_WAIT_STARTED status."""
        from arm.ripper.utils import database_updater
        database_updater({"status": "active"}, sample_job)
        response = client.post(f'/api/v1/jobs/{sample_job.job_id}/pause')
        assert response.status_code == 409

    def test_pause_toggles_on(self, client, sample_job, app_context):
        from arm.ripper.utils import database_updater
        from arm.database import db
        database_updater({"status": "waiting"}, sample_job)
        response = client.post(f'/api/v1/jobs/{sample_job.job_id}/pause')
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["paused"] is True
        db.session.refresh(sample_job)
        assert sample_job.manual_pause is True

    def test_pause_toggles_off(self, client, sample_job, app_context):
        from arm.ripper.utils import database_updater
        from arm.database import db
        database_updater({"status": "waiting", "manual_pause": True}, sample_job)
        response = client.post(f'/api/v1/jobs/{sample_job.job_id}/pause')
        assert response.status_code == 200
        data = response.json()
        assert data["paused"] is False
        db.session.refresh(sample_job)
        assert sample_job.manual_pause is False


class TestApiJobConfig:
    """Test PATCH /api/v1/jobs/<id>/config endpoint."""

    def test_change_config_nonexistent(self, client):
        response = client.patch(
            '/api/v1/jobs/99999/config',
            json={"RIPMETHOD": "mkv"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_change_config_empty_body(self, client, sample_job, app_context):
        response = client.patch(
            f'/api/v1/jobs/{sample_job.job_id}/config',
            json={},
        )
        assert response.status_code == 400

    def test_change_config_invalid_ripmethod(self, client, sample_job, app_context):
        response = client.patch(
            f'/api/v1/jobs/{sample_job.job_id}/config',
            json={"RIPMETHOD": "invalid"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "RIPMETHOD" in data["error"]

    def test_change_config_success(self, client, sample_job, app_context):
        response = client.patch(
            f'/api/v1/jobs/{sample_job.job_id}/config',
            json={"RIPMETHOD": "backup", "MAINFEATURE": True, "MINLENGTH": 600},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["job_id"] == sample_job.job_id


class TestApiJobFixPermissions:
    """Test POST /api/v1/jobs/<id>/fix-permissions endpoint."""

    def test_fix_permissions_with_mock(self, client):
        with unittest.mock.patch('arm.api.v1.jobs.svc_files') as mock_utils:
            mock_utils.fix_permissions.return_value = {"success": True}
            response = client.post('/api/v1/jobs/1/fix-permissions')
            assert response.status_code == 200


class TestApiJobSend:
    """Test POST /api/v1/jobs/<id>/send endpoint."""

    def test_send_with_mock(self, client):
        with unittest.mock.patch('arm.api.v1.jobs.svc_files') as mock_utils:
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
        data = response.json()
        assert data is not None


class TestApiSystemRestart:
    """Test POST /api/v1/system/restart endpoint."""

    def test_restart_returns_response(self, client):
        with unittest.mock.patch('arm.api.v1.system.svc_jobs') as mock_api:
            mock_api.restart_ui.return_value = {"success": True}
            response = client.post('/api/v1/system/restart')
            assert response.status_code == 200


class TestApiJobTitleUpdate:
    """Test PUT /api/v1/jobs/<id>/title endpoint."""

    def test_update_title_basic(self, client, sample_job, app_context):
        response = client.put(
            f'/api/v1/jobs/{sample_job.job_id}/title',
            json={"title": "New Title", "year": "2020"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["updated"]["title"] == "New Title"
        assert data["updated"]["year"] == "2020"

    def test_update_nonexistent_job(self, client):
        response = client.put(
            '/api/v1/jobs/99999/title',
            json={"title": "Test"},
        )
        assert response.status_code == 404

    def test_update_empty_body(self, client, sample_job, app_context):
        response = client.put(
            f'/api/v1/jobs/{sample_job.job_id}/title',
            json={},
        )
        assert response.status_code == 400

    def test_update_structured_fields_music(self, client, sample_job, app_context):
        """Sending artist/album stores them and re-renders the title."""
        response = client.put(
            f'/api/v1/jobs/{sample_job.job_id}/title',
            json={
                "artist": "The Beatles",
                "album": "Abbey Road",
                "year": "1969",
                "video_type": "music",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["updated"]["artist"] == "The Beatles"
        assert data["updated"]["album"] == "Abbey Road"
        # Title should be auto-rendered from the music pattern
        assert data["updated"]["title"] == "The Beatles - Abbey Road"

    def test_update_structured_fields_series(self, client, sample_job, app_context):
        """Sending season/episode stores them and re-renders the title."""
        # First set title and type so the pattern has something to work with
        sample_job.title = "Breaking Bad"
        sample_job.video_type = "series"
        from arm.database import db
        db.session.commit()

        response = client.put(
            f'/api/v1/jobs/{sample_job.job_id}/title',
            json={
                "season": "2",
                "episode": "5",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["updated"]["season"] == "2"
        assert data["updated"]["episode"] == "5"
        # Title re-rendered from TV pattern
        assert data["updated"]["title"] == "Breaking Bad S02E05"

    def test_explicit_title_not_overridden(self, client, sample_job, app_context):
        """When title is explicitly set alongside structured fields, it's not overridden."""
        response = client.put(
            f'/api/v1/jobs/{sample_job.job_id}/title',
            json={
                "title": "Custom Title",
                "artist": "Queen",
                "album": "Jazz",
                "video_type": "music",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Title should be the explicit value, not the pattern-rendered one
        assert data["updated"]["title"] == "Custom Title"

    def test_update_invalid_disctype(self, client, sample_job, app_context):
        response = client.put(
            f'/api/v1/jobs/{sample_job.job_id}/title',
            json={"disctype": "invalid"},
        )
        assert response.status_code == 400


class TestApiNamingPreview:
    """Test POST /api/v1/naming/preview endpoint."""

    def test_preview_basic(self, client):
        response = client.post(
            '/api/v1/naming/preview',
            json={
                "pattern": "{artist} - {album} ({year})",
                "variables": {"artist": "Queen", "album": "Jazz", "year": "1978"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rendered"] == "Queen - Jazz (1978)"

    def test_preview_missing_variable(self, client):
        response = client.post(
            '/api/v1/naming/preview',
            json={
                "pattern": "{title} ({year})",
                "variables": {"title": "Inception"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rendered"] == "Inception"

    def test_preview_empty_pattern(self, client):
        response = client.post(
            '/api/v1/naming/preview',
            json={"pattern": "", "variables": {}},
        )
        assert response.status_code == 400

    def test_preview_tv_pattern(self, client):
        response = client.post(
            '/api/v1/naming/preview',
            json={
                "pattern": "{title} S{season}E{episode}",
                "variables": {"title": "Lost", "season": "03", "episode": "12"},
            },
        )
        assert response.status_code == 200
        assert response.json()["rendered"] == "Lost S03E12"


class TestApiSettingsConfig:
    """Test GET /api/v1/settings/config endpoint."""

    def test_config_includes_naming_variables(self, client):
        response = client.get('/api/v1/settings/config')
        assert response.status_code == 200
        data = response.json()
        assert "naming_variables" in data
        nv = data["naming_variables"]
        assert isinstance(nv, dict)
        assert "title" in nv
        assert "year" in nv
        assert "artist" in nv
        assert "album" in nv
        assert "season" in nv
        assert "episode" in nv

    def test_naming_variables_match_engine(self, client):
        from arm.ripper.naming import PATTERN_VARIABLES
        response = client.get('/api/v1/settings/config')
        data = response.json()
        assert data["naming_variables"] == PATTERN_VARIABLES
