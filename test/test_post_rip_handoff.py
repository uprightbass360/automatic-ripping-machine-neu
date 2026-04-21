"""Tests for arm.ripper.arm_ripper._post_rip_handoff.

Covers the four post-rip outcomes:
  A. SKIP_TRANSCODE=true + transcoder configured -> SUCCESS + finalize_output
  B. SKIP_TRANSCODE=false + transcoder configured -> TRANSCODE_WAITING + webhook
  C. No transcoder configured -> SUCCESS + finalize_output
  D. Webhook send fails -> FAILURE

These tests exercise the helper directly without patching it in isolation,
catching the dual-writer bug in arm/ripper/main.py.
"""
from unittest.mock import MagicMock, patch

import pytest

from arm.ripper.arm_ripper import _post_rip_handoff
from arm.models.job import JobState


@pytest.fixture
def mock_job():
    """Return a minimal Job double."""
    job = MagicMock()
    job.title = "Test Movie"
    job.config = MagicMock()
    job.config.SKIP_TRANSCODE = None  # caller sets per-test
    job.config.NOTIFY_RIP = False
    job.status = JobState.VIDEO_RIPPING.value
    return job


@patch("arm.ripper.arm_ripper.utils.transcoder_notify")
@patch("arm.ripper.naming.finalize_output")
@patch("arm.ripper.arm_ripper.db")
@patch("arm.config.config.arm_config", {"TRANSCODER_URL": "http://transcoder", "SKIP_TRANSCODE": False})
def test_skip_true_with_transcoder_configured_sets_success(
    mock_db, mock_finalize, mock_notify, mock_job,
):
    """Outcome A: SKIP_TRANSCODE=true wins over transcoder being configured."""
    mock_job.config.SKIP_TRANSCODE = True

    _post_rip_handoff(mock_job)

    mock_finalize.assert_called_once_with(mock_job)
    assert mock_job.status == JobState.SUCCESS.value
    mock_notify.assert_not_called()  # no webhook when skipping


@patch("arm.ripper.arm_ripper.utils.transcoder_notify")
@patch("arm.ripper.naming.finalize_output")
@patch("arm.ripper.arm_ripper.db")
@patch("arm.config.config.arm_config", {"TRANSCODER_URL": "http://transcoder", "SKIP_TRANSCODE": False})
def test_skip_false_with_transcoder_configured_sets_waiting(
    mock_db, mock_finalize, mock_notify, mock_job,
):
    """Outcome B: webhook fires AND status is TRANSCODE_WAITING.

    This is the test that fails today - the current implementation
    only fires the webhook but does not write TRANSCODE_WAITING.
    """
    mock_job.config.SKIP_TRANSCODE = False

    _post_rip_handoff(mock_job)

    mock_finalize.assert_not_called()
    mock_notify.assert_called_once()  # webhook fired
    assert mock_job.status == JobState.TRANSCODE_WAITING.value


@patch("arm.ripper.arm_ripper.utils.transcoder_notify")
@patch("arm.ripper.naming.finalize_output")
@patch("arm.ripper.arm_ripper.db")
@patch("arm.config.config.arm_config", {"TRANSCODER_URL": "", "SKIP_TRANSCODE": False})
def test_no_transcoder_configured_sets_success(
    mock_db, mock_finalize, mock_notify, mock_job,
):
    """Outcome C: empty TRANSCODER_URL -> finalize locally, SUCCESS."""
    mock_job.config.SKIP_TRANSCODE = False

    _post_rip_handoff(mock_job)

    mock_finalize.assert_called_once_with(mock_job)
    assert mock_job.status == JobState.SUCCESS.value
    mock_notify.assert_not_called()


@patch("arm.ripper.arm_ripper.utils.transcoder_notify")
@patch("arm.ripper.naming.finalize_output")
@patch("arm.ripper.arm_ripper.db")
@patch("arm.config.config.arm_config", {"TRANSCODER_URL": "http://transcoder", "SKIP_TRANSCODE": False})
def test_webhook_failure_sets_failure_status(
    mock_db, mock_finalize, mock_notify, mock_job,
):
    """Outcome D: webhook send raises -> job marked FAILURE, not WAITING.

    A failed handoff should not look like a pending one.
    """
    mock_job.config.SKIP_TRANSCODE = False
    mock_notify.side_effect = Exception("transcoder unreachable")

    _post_rip_handoff(mock_job)

    assert mock_job.status == JobState.FAILURE.value
    mock_finalize.assert_not_called()


@patch("arm.ripper.arm_ripper.utils.transcoder_notify")
@patch("arm.ripper.naming.finalize_output")
@patch("arm.ripper.arm_ripper.db")
@patch("arm.config.config.arm_config", {"TRANSCODER_URL": "http://transcoder", "SKIP_TRANSCODE": True})
def test_global_skip_used_when_per_job_is_none(
    mock_db, mock_finalize, mock_notify, mock_job,
):
    """Fallback: per-job config.SKIP_TRANSCODE=None -> global wins."""
    mock_job.config.SKIP_TRANSCODE = None

    _post_rip_handoff(mock_job)

    mock_finalize.assert_called_once_with(mock_job)
    assert mock_job.status == JobState.SUCCESS.value
