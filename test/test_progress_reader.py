"""Tests for arm/services/progress_reader.py - MakeMKV + abcde progress."""
import unittest.mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from arm.services import progress_reader


@pytest.fixture
def progress_dir(tmp_path):
    log_dir = tmp_path / "logs"
    (log_dir / "progress").mkdir(parents=True)
    with unittest.mock.patch("arm.config.config.arm_config", {"LOGPATH": str(log_dir)}):
        yield log_dir


class TestRipProgress:
    def test_no_file_returns_none(self, progress_dir):
        result = progress_reader.get_rip_progress(99)
        assert result == {"progress": None, "stage": None, "tracks_ripped": None}

    def test_prgv_during_save_phase(self, progress_dir):
        (progress_dir / "progress" / "1.log").write_text(
            'PRGT:0,0,"Saving to MKV file"\n'
            "PRGV:5000,7500,10000\n"
        )
        result = progress_reader.get_rip_progress(1)
        assert result["progress"] == 75.0

    def test_prgc_advances_stage_and_tracks(self, progress_dir):
        (progress_dir / "progress" / "2.log").write_text(
            'PRGC:0,2,"Saving to MKV file"\n'
            "PRGV:1000,2000,10000\n"
        )
        result = progress_reader.get_rip_progress(2)
        assert result["stage"] == "Title 3: Saving to MKV file"
        assert result["tracks_ripped"] == 2

    def test_zero_max_skipped(self, progress_dir):
        (progress_dir / "progress" / "3.log").write_text("PRGV:0,0,0\n")
        result = progress_reader.get_rip_progress(3)
        assert result["progress"] is None

    def test_oserror_on_open_returns_default(self, progress_dir, monkeypatch):
        target = progress_dir / "progress" / "4.log"
        target.write_text("PRGV:1,1,2\n")

        import builtins
        real_open = builtins.open

        def boom(path, *a, **kw):
            if str(path).endswith("4.log"):
                raise OSError("nope")
            return real_open(path, *a, **kw)

        monkeypatch.setattr(builtins, "open", boom)
        result = progress_reader.get_rip_progress(4)
        assert result == {"progress": None, "stage": None, "tracks_ripped": None}

    def test_traversal_returns_none(self, progress_dir):
        # _safe_log_path coerces to None for paths escaping LOGPATH
        result = progress_reader._safe_log_path("..", "..", "etc", "passwd")
        assert result is None


class TestMusicProgress:
    def test_no_logfile(self, progress_dir):
        result = progress_reader.get_music_progress(None, 10)
        assert result["progress"] is None
        assert result["stage"] is None

    def test_missing_file(self, progress_dir):
        result = progress_reader.get_music_progress("nonexistent.log", 10)
        assert result["progress"] is None

    def test_parses_abcde_phases(self, progress_dir):
        (progress_dir / "music.log").write_text(
            "Grabbing track 1: foo\n"
            "Grabbing track 2: bar\n"
            "Encoding track 1 of 5\n"
            "Encoding track 2 of 5\n"
            "Tagging track 1 of 5\n"
        )
        result = progress_reader.get_music_progress("music.log", 5)
        assert result["tracks_total"] == 5
        assert result["tracks_ripped"] == 2  # encoding count
        assert result["progress"] == 40.0
        assert "tagging track 2" in result["stage"]

    def test_empty_log_returns_default(self, progress_dir):
        (progress_dir / "music.log").write_text("nothing here\n")
        result = progress_reader.get_music_progress("music.log", 5)
        assert result["progress"] is None

    def test_falls_back_to_seen_count_when_total_zero(self, progress_dir):
        (progress_dir / "music.log").write_text("Grabbing track 1: foo\n")
        result = progress_reader.get_music_progress("music.log", 0)
        assert result["tracks_total"] == 1


class TestProgressStateEndpoint:
    @pytest.fixture
    def jobs_client(self, progress_dir, app_context):
        from arm.api.v1.jobs import router
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as c:
            yield c, progress_dir

    def test_endpoint_includes_realtime_keys(self, jobs_client, sample_job):
        client, log_dir = jobs_client
        # MakeMKV progress for the job
        (log_dir / "progress" / f"{sample_job.job_id}.log").write_text(
            'PRGT:0,0,"Saving to MKV file"\n'
            "PRGV:1000,5000,10000\n"
        )
        resp = client.get(f"/api/v1/jobs/{sample_job.job_id}/progress-state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["rip_progress"] == 50.0
        assert body["rip_stage"] is None  # no PRGC, name was "Saving"
        # Pre-existing keys still present
        assert body["disctype"] == "bluray"
        assert body["logfile"] == "test.log"
        assert "track_counts" in body
        # Music keys present (None for video disc)
        assert body["music_progress"] is None

    def test_endpoint_with_no_progress_file(self, jobs_client, sample_job):
        client, _ = jobs_client
        resp = client.get(f"/api/v1/jobs/{sample_job.job_id}/progress-state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["rip_progress"] is None
        assert body["tracks_ripped_realtime"] is None
        assert body["music_progress"] is None

    def test_missing_job_404(self, jobs_client):
        client, _ = jobs_client
        resp = client.get("/api/v1/jobs/99999/progress-state")
        assert resp.status_code == 404
