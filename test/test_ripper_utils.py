"""Tests for arm/ripper/utils.py transcoder_notify() webhook behavior.

Specifically verifies the cross-service version handshake: ARM must stamp
every webhook POST to the transcoder with ``X-Api-Version: 2`` so older
transcoders reject new-shape payloads loudly instead of silently dropping
unknown fields.
"""
import unittest.mock


class TestTranscoderNotifyApiVersionHeader:
    """Task 5: transcoder_notify must send X-Api-Version: 2."""

    def test_sends_x_api_version_header(self, app_context):
        from arm.ripper.utils import transcoder_notify

        cfg = {
            'TRANSCODER_URL': 'http://localhost:5000/webhook',
            'TRANSCODER_WEBHOOK_SECRET': 'test-secret',
            'SHARED_RAW_PATH': '',
            'LOCAL_RAW_PATH': '',
        }
        job = unittest.mock.MagicMock()
        job.job_id = 1
        job.raw_path = '/home/arm/media/raw/Movie'
        job.video_type = 'movie'
        job.year = '2024'
        job.disctype = 'bluray'
        job.status = 'active'
        job.poster_url = ''
        job.title = 'Movie'
        job.multi_title = False
        job.transcode_overrides = None

        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 200

        with unittest.mock.patch('httpx.Client') as mock_client_cls, \
             unittest.mock.patch('arm.ripper.utils._build_webhook_payload',
                                 return_value={"title": "test"}), \
             unittest.mock.patch('arm.ripper.utils.db'):
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.post.return_value = mock_resp
            transcoder_notify(cfg, "Title", "Body", job)

        mock_client.post.assert_called_once()
        _, kwargs = mock_client.post.call_args
        headers = kwargs.get('headers') or {}
        assert headers.get('X-Api-Version') == '2', (
            f"Expected X-Api-Version: 2 header, got headers={headers!r}"
        )

    def test_sends_x_api_version_header_without_secret(self, app_context):
        """Header must be set even when no webhook secret is configured."""
        from arm.ripper.utils import transcoder_notify

        cfg = {
            'TRANSCODER_URL': 'http://localhost:5000/webhook',
            'TRANSCODER_WEBHOOK_SECRET': '',
            'SHARED_RAW_PATH': '',
            'LOCAL_RAW_PATH': '',
        }
        job = unittest.mock.MagicMock()
        job.job_id = 2
        job.raw_path = '/home/arm/media/raw/OtherMovie'
        job.video_type = 'movie'
        job.year = '2024'
        job.disctype = 'bluray'
        job.status = 'active'
        job.poster_url = ''
        job.title = 'OtherMovie'
        job.multi_title = False
        job.transcode_overrides = None

        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 200

        with unittest.mock.patch('httpx.Client') as mock_client_cls, \
             unittest.mock.patch('arm.ripper.utils._build_webhook_payload',
                                 return_value={"title": "test"}), \
             unittest.mock.patch('arm.ripper.utils.db'):
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.post.return_value = mock_resp
            transcoder_notify(cfg, "Title", "Body", job)

        _, kwargs = mock_client.post.call_args
        headers = kwargs.get('headers') or {}
        assert headers.get('X-Api-Version') == '2'
