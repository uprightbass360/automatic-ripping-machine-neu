"""Tests for arm/ripper/utils.py transcoder_notify() webhook behavior."""
import unittest.mock

import pytest


@pytest.mark.parametrize("webhook_secret", ["test-secret", ""])
def test_transcoder_notify_sends_x_api_version_header(webhook_secret, app_context):
    """transcoder_notify must send X-Api-Version: 2 regardless of webhook secret.

    Cross-service version handshake: ARM stamps every webhook POST to the
    transcoder so older transcoders reject new-shape payloads loudly instead
    of silently dropping unknown fields.
    """
    from arm.ripper.utils import transcoder_notify

    cfg = {
        'TRANSCODER_URL': 'https://localhost:5000/webhook',
        'TRANSCODER_WEBHOOK_SECRET': webhook_secret,
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
