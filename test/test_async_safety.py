"""Tests for async API safety improvements.

Covers: database_updater exponential backoff, session cleanup in daemon
threads, TVDB token lock, arm_config lock, async endpoint wrappers,
and send_to_remote_db timeout.
"""
import asyncio
import unittest.mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(app_context):
    """FastAPI test client."""
    from arm.app import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# =====================================================================
# database_updater - exponential backoff
# =====================================================================


class TestDatabaseUpdaterBackoff:
    """Test exponential backoff in database_updater."""

    def test_backoff_increases_sleep_duration(self, app_context):
        """Sleep durations should increase exponentially."""
        from arm.services.files import database_updater

        sleep_calls = []
        call_count = 0

        def commit_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise Exception("database is locked")

        def mock_sleep(duration):
            sleep_calls.append(duration)

        job = unittest.mock.MagicMock()
        with unittest.mock.patch("arm.services.files.db") as mock_db, \
             unittest.mock.patch("arm.services.files.sleep", side_effect=mock_sleep):
            mock_db.session.commit.side_effect = commit_side_effect
            result = database_updater({"status": "x"}, job, wait_time=10)

        assert result is True
        assert len(sleep_calls) == 3
        # Exponential: 0.1, 0.2, 0.4
        assert sleep_calls[0] == pytest.approx(0.1)
        assert sleep_calls[1] == pytest.approx(0.2)
        assert sleep_calls[2] == pytest.approx(0.4)

    def test_backoff_caps_at_two_seconds(self, app_context):
        """Sleep duration should not exceed 2 seconds."""
        from arm.services.files import database_updater

        sleep_calls = []
        call_count = 0

        def commit_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 20:
                raise Exception("database is locked")

        def mock_sleep(duration):
            sleep_calls.append(duration)

        job = unittest.mock.MagicMock()
        with unittest.mock.patch("arm.services.files.db") as mock_db, \
             unittest.mock.patch("arm.services.files.sleep", side_effect=mock_sleep):
            mock_db.session.commit.side_effect = commit_side_effect
            database_updater({"status": "x"}, job, wait_time=60)

        # After enough doublings (0.1, 0.2, 0.4, 0.8, 1.6, 2.0, 2.0, ...),
        # all subsequent sleeps should be capped at 2.0
        for duration in sleep_calls:
            assert duration <= 2.0

    def test_default_wait_time_is_ten(self, app_context):
        """API callers get 10s default, not the old 90s."""
        from arm.services.files import database_updater
        import inspect

        sig = inspect.signature(database_updater)
        assert sig.parameters["wait_time"].default == 10

    def test_ripper_delegates_with_high_wait_time(self, app_context):
        """Ripper's database_updater passes wait_time=90 by default."""
        from arm.ripper.utils import database_updater
        import inspect

        sig = inspect.signature(database_updater)
        assert sig.parameters["wait_time"].default == 90

    def test_non_dict_returns_false(self, app_context):
        """Non-dict args should trigger rollback and return False."""
        from arm.services.files import database_updater

        job = unittest.mock.MagicMock()
        with unittest.mock.patch("arm.services.files.db") as mock_db:
            result = database_updater("not a dict", job)

        assert result is False
        mock_db.session.rollback.assert_called_once()

    def test_none_returns_false(self, app_context):
        """None args should trigger rollback and return False."""
        from arm.services.files import database_updater

        job = unittest.mock.MagicMock()
        with unittest.mock.patch("arm.services.files.db") as mock_db:
            result = database_updater(None, job)

        assert result is False
        mock_db.session.rollback.assert_called_once()

    def test_sensitive_keys_redacted_in_log(self, app_context):
        """Sensitive keys should log '<redacted>' instead of the value."""
        from arm.services.files import database_updater

        job = unittest.mock.MagicMock()
        with unittest.mock.patch("arm.services.files.db"), \
             unittest.mock.patch("arm.services.files.log") as mock_log:
            database_updater({"omdb_api_key": "secret123"}, job)

        # Find the debug call for the key
        debug_calls = [str(c) for c in mock_log.debug.call_args_list]
        assert any("<redacted>" in c for c in debug_calls)
        assert not any("secret123" in c for c in debug_calls)

    def test_timeout_raises_runtime_error(self, app_context):
        """Exhausting wait_time should raise RuntimeError, not return True."""
        from arm.services.files import database_updater

        job = unittest.mock.MagicMock()
        with unittest.mock.patch("arm.services.files.db") as mock_db, \
             unittest.mock.patch("arm.services.files.sleep"):
            mock_db.session.commit.side_effect = Exception("database is locked")
            with pytest.raises(RuntimeError, match="timed out"):
                database_updater({"status": "x"}, job, wait_time=0.5)
            mock_db.session.rollback.assert_called_once()


# =====================================================================
# _rip_folder_by_id - session cleanup
# =====================================================================


class TestRipFolderSessionCleanup:
    """Test that _rip_folder_by_id cleans up the DB session."""

    def test_session_removed_on_success(self, app_context, sample_job):
        """db.session.remove() called after successful rip."""
        from arm.api.v1.jobs import _rip_folder_by_id

        with unittest.mock.patch("arm.api.v1.jobs.rip_folder") as mock_rip, \
             unittest.mock.patch("arm.api.v1.jobs.db") as mock_db:
            mock_db.session.remove = unittest.mock.MagicMock()
            # Provide a real Job.query.get that returns something
            mock_job = unittest.mock.MagicMock()
            with unittest.mock.patch("arm.api.v1.jobs.Job") as MockJob:
                MockJob.query.get.return_value = mock_job
                _rip_folder_by_id(1)

            mock_rip.assert_called_once_with(mock_job)
            mock_db.session.remove.assert_called_once()

    def test_session_removed_on_exception(self, app_context):
        """db.session.remove() called even when rip_folder raises."""
        from arm.api.v1.jobs import _rip_folder_by_id

        with unittest.mock.patch("arm.api.v1.jobs.rip_folder", side_effect=RuntimeError("boom")), \
             unittest.mock.patch("arm.api.v1.jobs.db") as mock_db:
            mock_db.session.remove = unittest.mock.MagicMock()
            mock_job = unittest.mock.MagicMock()
            with unittest.mock.patch("arm.api.v1.jobs.Job") as MockJob:
                MockJob.query.get.return_value = mock_job
                with pytest.raises(RuntimeError, match="boom"):
                    _rip_folder_by_id(1)

            mock_db.session.remove.assert_called_once()

    def test_session_removed_when_job_not_found(self, app_context):
        """db.session.remove() called even when job is not found."""
        from arm.api.v1.jobs import _rip_folder_by_id

        with unittest.mock.patch("arm.api.v1.jobs.db") as mock_db:
            mock_db.session.remove = unittest.mock.MagicMock()
            with unittest.mock.patch("arm.api.v1.jobs.Job") as MockJob:
                MockJob.query.get.return_value = None
                _rip_folder_by_id(999)

            mock_db.session.remove.assert_called_once()


# =====================================================================
# TVDB token lock
# =====================================================================


class TestTvdbTokenLock:
    """Test that TVDB token acquisition is protected by asyncio.Lock."""

    def test_lock_exists(self):
        """Module should have an asyncio.Lock for token management."""
        from arm.services import tvdb
        assert isinstance(tvdb._TOKEN_LOCK, asyncio.Lock)

    def test_concurrent_token_requests_serialized(self):
        """Multiple concurrent _ensure_token calls should not race."""
        from arm.services import tvdb

        tvdb._TOKEN = None
        tvdb._TOKEN_EXPIRES = 0

        call_count = 0

        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"data": {"token": "serialized_token"}}
        mock_response.raise_for_status = unittest.mock.MagicMock()

        async def mock_post(url, json=None):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # simulate network latency
            return mock_response

        mock_client = unittest.mock.MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = unittest.mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)

        async def run_concurrent():
            with unittest.mock.patch("arm.services.tvdb.cfg.arm_config",
                                     {"TVDB_API_KEY": "test_key"}), \
                 unittest.mock.patch("arm.services.tvdb.httpx.AsyncClient",
                                     return_value=mock_client):
                # Launch 5 concurrent calls
                tasks = [tvdb._ensure_token() for _ in range(5)]
                tokens = await asyncio.gather(*tasks)
            return tokens

        tokens = asyncio.run(run_concurrent())

        # All should get the same token
        assert all(t == "serialized_token" for t in tokens)
        # Lock serializes: first call fetches, rest reuse cached
        assert call_count == 1

        # Cleanup
        tvdb._TOKEN = None
        tvdb._TOKEN_EXPIRES = 0


# =====================================================================
# arm_config lock
# =====================================================================


class TestArmConfigLock:
    """Test that config updates use threading.Lock."""

    def test_lock_exists(self):
        """Config module should expose arm_config_lock."""
        import arm.config.config as cfg
        # threading.Lock() returns a _thread.lock instance
        assert hasattr(cfg, 'arm_config_lock')
        assert hasattr(cfg.arm_config_lock, 'acquire')
        assert hasattr(cfg.arm_config_lock, 'release')

    def test_settings_update_uses_lock(self):
        """update_config code path acquires arm_config_lock around clear+update."""
        import arm.api.v1.settings  # ensure module is loaded

        import inspect
        source = inspect.getsource(arm.api.v1.settings.update_config)
        assert "arm_config_lock" in source, (
            "update_config must use cfg.arm_config_lock"
        )

    def test_change_job_config_uses_lock(self):
        """change_job_config applies config_updates under arm_config_lock."""
        import arm.api.v1.jobs  # ensure module is loaded

        import inspect
        source = inspect.getsource(arm.api.v1.jobs.change_job_config)
        assert "arm_config_lock" in source, (
            "change_job_config must use cfg.arm_config_lock"
        )


# =====================================================================
# Async endpoint wrappers
# =====================================================================


class TestAsyncEndpoints:
    """Test that heavy endpoints are async and work correctly."""

    def test_fix_permissions_is_async(self):
        """fix_job_permissions should be an async def."""
        import inspect
        from arm.api.v1.jobs import fix_job_permissions
        assert inspect.iscoroutinefunction(fix_job_permissions)

    def test_send_job_is_async(self):
        """send_job should be an async def."""
        import inspect
        from arm.api.v1.jobs import send_job
        assert inspect.iscoroutinefunction(send_job)

    def test_rescan_drives_is_async(self):
        """rescan_drives should be an async def."""
        import inspect
        from arm.api.v1.drives import rescan_drives
        assert inspect.iscoroutinefunction(rescan_drives)

    def test_maintenance_delete_log_is_async(self):
        import inspect
        from arm.api.v1.maintenance import delete_log
        assert inspect.iscoroutinefunction(delete_log)

    def test_maintenance_delete_folder_is_async(self):
        import inspect
        from arm.api.v1.maintenance import delete_folder
        assert inspect.iscoroutinefunction(delete_folder)

    def test_maintenance_bulk_delete_logs_is_async(self):
        import inspect
        from arm.api.v1.maintenance import bulk_delete_logs
        assert inspect.iscoroutinefunction(bulk_delete_logs)

    def test_maintenance_bulk_delete_folders_is_async(self):
        import inspect
        from arm.api.v1.maintenance import bulk_delete_folders
        assert inspect.iscoroutinefunction(bulk_delete_folders)

    def test_maintenance_clear_raw_is_async(self):
        import inspect
        from arm.api.v1.maintenance import clear_raw
        assert inspect.iscoroutinefunction(clear_raw)

    def test_fix_permissions_via_client(self, app_context, client, sample_job):
        """POST /jobs/{id}/fix-permissions should work through async wrapper."""
        with unittest.mock.patch("arm.api.v1.jobs.svc_files.fix_permissions",
                                 return_value={"success": True, "mode": "fixperms"}):
            resp = client.post(f"/api/v1/jobs/{sample_job.job_id}/fix-permissions")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_rescan_drives_via_client(self, app_context, client):
        """POST /drives/rescan should work through async wrapper."""
        with unittest.mock.patch("arm.services.drives.drives_update", return_value=0), \
             unittest.mock.patch("arm.api.v1.drives.SystemDrives") as mock_sd:
            mock_sd.query.count.return_value = 2
            resp = client.post("/api/v1/drives/rescan")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# =====================================================================
# send_to_remote_db timeout
# =====================================================================


class TestSendToRemoteDbTimeout:
    """Test that send_to_remote_db passes timeout to requests."""

    def test_requests_get_called_with_timeout(self, app_context):
        from arm.services.files import send_to_remote_db

        mock_job = unittest.mock.MagicMock()
        mock_job.crc_id = "abc"
        mock_job.title = "Test"
        mock_job.year = "2020"
        mock_job.imdb_id = "tt1234"
        mock_job.hasnicetitle = True
        mock_job.label = "TEST"
        mock_job.video_type = "movie"
        mock_job.get_d.return_value = {"title": "Test"}
        mock_job.config.get_d.return_value = {}

        mock_response = unittest.mock.MagicMock()
        mock_response.text = '{"success": true}'

        with unittest.mock.patch("arm.services.files.Job") as MockJob, \
             unittest.mock.patch("arm.services.files.cfg") as mock_cfg, \
             unittest.mock.patch("arm.services.files.requests.get",
                                 return_value=mock_response) as mock_get:
            mock_cfg.arm_config = {"ARM_API_KEY": "key"}
            MockJob.query.get.return_value = mock_job
            send_to_remote_db(1)

        # Verify timeout=15 was passed
        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 15


# =====================================================================
# Ripper database_updater delegation
# =====================================================================


class TestRipperDelegation:
    """Test that ripper's database_updater delegates to services version."""

    def test_delegates_to_services(self, app_context):
        """ripper.utils.database_updater should call services.files.database_updater."""
        with unittest.mock.patch("arm.services.files.database_updater",
                                 return_value=True) as mock_svc:
            from arm.ripper.utils import database_updater
            job = unittest.mock.MagicMock()
            result = database_updater({"status": "x"}, job, wait_time=30)

        mock_svc.assert_called_once_with({"status": "x"}, job, wait_time=30)
        assert result is True

    def test_delegation_preserves_non_dict_behavior(self, app_context):
        """Non-dict args should still return False via delegation."""
        with unittest.mock.patch("arm.services.files.database_updater",
                                 return_value=False) as mock_svc:
            from arm.ripper.utils import database_updater
            job = unittest.mock.MagicMock()
            result = database_updater(False, job)

        mock_svc.assert_called_once()
        assert result is False
