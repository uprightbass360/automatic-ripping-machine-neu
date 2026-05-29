"""Disabled tracks (track.enabled == False) must not be sent to the transcoder."""
from arm.database import db
from arm.models.track import Track


def _add_track(job, number, enabled):
    t = Track(job.job_id, number, 3600, '16:9', 24.0, False, 'makemkv',
              f'title{number}', f'title{number}.mkv')
    t.enabled = enabled
    t.ripped = True
    db.session.add(t)
    return t


class TestWebhookManifestHonorsEnabled:
    def test_disabled_track_excluded_from_manifest(self, app_context, sample_job):
        from arm.ripper.utils import _build_webhook_payload
        sample_job.multi_title = True
        _add_track(sample_job, '1', enabled=True)
        _add_track(sample_job, '2', enabled=False)
        _add_track(sample_job, '3', enabled=None)  # legacy NULL -> include
        db.session.commit()

        payload = _build_webhook_payload("done", "body", sample_job, "raw_dir")
        numbers = {t["track_number"] for t in (payload.get("tracks") or [])}
        assert numbers == {"1", "3"}, f"disabled track 2 must be excluded, got {numbers}"

    def test_all_disabled_falls_back_to_all_tracks(self, app_context, sample_job):
        from arm.ripper.utils import _build_webhook_payload
        sample_job.multi_title = True
        _add_track(sample_job, '1', enabled=False)
        _add_track(sample_job, '2', enabled=False)
        db.session.commit()

        payload = _build_webhook_payload("done", "body", sample_job, "raw_dir")
        numbers = {t["track_number"] for t in (payload.get("tracks") or [])}
        assert numbers == {"1", "2"}, "all-disabled must fall back to sending all tracks"
