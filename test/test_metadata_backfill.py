"""Tests for arm.services.metadata_backfill: best-effort one-shot backfill
of the media_metadata_auto blob for pre-Phase-2 jobs."""
import asyncio
import unittest.mock

import pytest

from arm.database import db
from arm.services.metadata import MetadataConfigError
from arm.services.metadata_backfill import (
    _candidate_job_ids,
    _legacy_dict_to_metadata,
    backfill_media_metadata,
)


def _run(coro):
    return asyncio.run(coro)


class TestCandidateQuery:
    def test_skips_jobs_with_blob(self, app_context, sample_job):
        from arm_contracts import MediaMetadata
        sample_job.imdb_id = "tt1234567"
        sample_job.set_metadata_auto(MediaMetadata(poster_url="x"))
        db.session.commit()
        assert _candidate_job_ids() == []

    def test_skips_jobs_without_imdb_id(self, app_context, sample_job):
        sample_job.imdb_id = None
        db.session.commit()
        assert _candidate_job_ids() == []

    def test_includes_jobs_with_imdb_no_blob(self, app_context, sample_job):
        sample_job.imdb_id = "tt7654321"
        sample_job.media_metadata_auto = None
        db.session.commit()
        assert _candidate_job_ids() == [(sample_job.job_id, "tt7654321")]


class TestLegacyDictConversion:
    def test_video_type_movie_normalized_to_enum(self):
        meta = _legacy_dict_to_metadata({
            "poster_url": "http://example.com/p.jpg",
            "video_type": "movie",
            "imdb_id": "tt1",
        })
        from arm_contracts.enums import VideoType
        assert meta.poster_url == "http://example.com/p.jpg"
        assert meta.video_type == VideoType.movie

    def test_unknown_video_type_normalized_to_none(self):
        meta = _legacy_dict_to_metadata({"poster_url": "p", "video_type": "garbage"})
        assert meta.video_type is None

    def test_unknown_keys_silently_dropped(self):
        # If the adapter starts emitting a new key before the contract
        # adds it, the backfill should not crash.
        meta = _legacy_dict_to_metadata({"poster_url": "p", "future_field": "value"})
        assert meta.poster_url == "p"


class TestBackfillEndToEnd:
    def test_no_candidates_is_noop(self, app_context, sample_job):
        from arm_contracts import MediaMetadata
        sample_job.imdb_id = "tt1"
        sample_job.set_metadata_auto(MediaMetadata(poster_url="already"))
        db.session.commit()
        # Should complete without calling the adapter at all.
        with unittest.mock.patch("arm.services.metadata_backfill.metadata.get_details") as m:
            _run(backfill_media_metadata())
            m.assert_not_called()

    def test_successful_fetch_writes_blob(self, app_context, sample_job):
        sample_job.imdb_id = "tt2"
        sample_job.media_metadata_auto = None
        db.session.commit()
        async def fake_details(imdb_id):
            return {"poster_url": "http://api/poster.jpg", "imdb_id": imdb_id, "video_type": "movie"}
        with unittest.mock.patch("arm.services.metadata_backfill.metadata.get_details", side_effect=fake_details):
            _run(backfill_media_metadata())
        db.session.refresh(sample_job)
        assert sample_job.media_metadata_auto is not None
        assert "http://api/poster.jpg" in sample_job.media_metadata_auto

    def test_network_error_leaves_blob_empty(self, app_context, sample_job):
        sample_job.imdb_id = "tt3"
        sample_job.media_metadata_auto = None
        db.session.commit()
        async def boom(imdb_id):
            raise RuntimeError("network down")
        with unittest.mock.patch("arm.services.metadata_backfill.metadata.get_details", side_effect=boom):
            _run(backfill_media_metadata())
        db.session.refresh(sample_job)
        assert sample_job.media_metadata_auto in (None, "")

    def test_config_error_leaves_blob_empty(self, app_context, sample_job):
        sample_job.imdb_id = "tt4"
        sample_job.media_metadata_auto = None
        db.session.commit()
        async def no_key(imdb_id):
            raise MetadataConfigError("no key configured")
        with unittest.mock.patch("arm.services.metadata_backfill.metadata.get_details", side_effect=no_key):
            _run(backfill_media_metadata())
        db.session.refresh(sample_job)
        assert sample_job.media_metadata_auto in (None, "")

    def test_empty_adapter_result_leaves_blob_empty(self, app_context, sample_job):
        sample_job.imdb_id = "tt5"
        sample_job.media_metadata_auto = None
        db.session.commit()
        async def empty(imdb_id):
            return None
        with unittest.mock.patch("arm.services.metadata_backfill.metadata.get_details", side_effect=empty):
            _run(backfill_media_metadata())
        db.session.refresh(sample_job)
        assert sample_job.media_metadata_auto in (None, "")
