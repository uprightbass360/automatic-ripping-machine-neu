"""Tests for FFmpeg pure-logic functions (arm/ripper/ffmpeg.py)."""
import json
import unittest.mock

import pytest


class TestParseFps:
    """Test _parse_fps() frame rate string parsing."""

    def test_fraction_format(self):
        from arm.ripper.ffmpeg import _parse_fps

        result = _parse_fps("30000/1001")
        assert abs(result - 29.97) < 0.01

    def test_integer_fraction(self):
        from arm.ripper.ffmpeg import _parse_fps

        result = _parse_fps("25/1")
        assert result == 25.0

    def test_plain_number(self):
        from arm.ripper.ffmpeg import _parse_fps

        result = _parse_fps("24")
        assert result == 24.0

    def test_zero_over_zero(self):
        from arm.ripper.ffmpeg import _parse_fps

        result = _parse_fps("0/0")
        assert result == 0.0

    def test_none_input(self):
        from arm.ripper.ffmpeg import _parse_fps

        result = _parse_fps(None)
        assert result == 0.0

    def test_empty_string(self):
        from arm.ripper.ffmpeg import _parse_fps

        result = _parse_fps("")
        assert result == 0.0

    def test_garbage_input(self):
        from arm.ripper.ffmpeg import _parse_fps

        result = _parse_fps("not_a_number")
        assert result == 0.0


class TestComputeAspect:
    """Test _compute_aspect() aspect ratio calculation."""

    def test_16_9(self):
        from arm.ripper.ffmpeg import _compute_aspect

        result = _compute_aspect(1920, 1080)
        assert result == 1.78

    def test_4_3(self):
        from arm.ripper.ffmpeg import _compute_aspect

        result = _compute_aspect(640, 480)
        assert result == 1.33

    def test_2_35_1(self):
        from arm.ripper.ffmpeg import _compute_aspect

        result = _compute_aspect(1920, 817)
        assert result == 2.35

    def test_none_width(self):
        from arm.ripper.ffmpeg import _compute_aspect

        result = _compute_aspect(None, 1080)
        assert result == 0

    def test_none_height(self):
        from arm.ripper.ffmpeg import _compute_aspect

        result = _compute_aspect(1920, None)
        assert result == 0

    def test_zero_height(self):
        from arm.ripper.ffmpeg import _compute_aspect

        result = _compute_aspect(1920, 0)
        assert result == 0


class TestParseProbeOutput:
    """Test parse_probe_output() ffprobe JSON parsing."""

    def _make_probe_json(self, streams=None, duration="7200.5"):
        """Helper to build ffprobe-like JSON."""
        data = {
            "format": {"duration": duration, "format_name": "matroska"},
            "streams": streams or [],
        }
        return json.dumps(data)

    def test_single_video_stream(self):
        from arm.ripper.ffmpeg import parse_probe_output

        probe = self._make_probe_json(streams=[{
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "24000/1001",
            "duration": "5400.0",
            "index": 0,
        }])
        tracks = parse_probe_output(probe)
        assert len(tracks) == 1
        assert tracks[0]["title"] == 1
        assert tracks[0]["duration"] == 5400
        assert abs(tracks[0]["fps"] - 23.976) < 0.01
        assert tracks[0]["aspect"] == 1.78
        assert tracks[0]["codec"] == "h264"
        assert tracks[0]["stream_index"] == 0

    def test_multiple_video_streams(self):
        from arm.ripper.ffmpeg import parse_probe_output

        probe = self._make_probe_json(streams=[
            {"codec_type": "video", "codec_name": "h264",
             "width": 1920, "height": 1080, "r_frame_rate": "25/1",
             "duration": "3600", "index": 0},
            {"codec_type": "audio", "codec_name": "aac", "index": 1},
            {"codec_type": "video", "codec_name": "h265",
             "width": 3840, "height": 2160, "r_frame_rate": "30/1",
             "duration": "1800", "index": 2},
        ])
        tracks = parse_probe_output(probe)
        assert len(tracks) == 2
        assert tracks[0]["title"] == 1
        assert tracks[1]["title"] == 2
        assert tracks[1]["codec"] == "h265"

    def test_no_video_streams_fallback(self):
        from arm.ripper.ffmpeg import parse_probe_output

        probe = self._make_probe_json(streams=[
            {"codec_type": "audio", "codec_name": "aac", "index": 0},
        ], duration="120.5")
        tracks = parse_probe_output(probe)
        assert len(tracks) == 1
        assert tracks[0]["title"] == 1
        assert tracks[0]["duration"] == 120
        assert tracks[0]["fps"] == 0.0
        assert tracks[0]["codec"] == "matroska"

    def test_stream_without_duration_uses_container(self):
        from arm.ripper.ffmpeg import parse_probe_output

        probe = self._make_probe_json(streams=[{
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1280,
            "height": 720,
            "r_frame_rate": "25/1",
            "index": 0,
            # no "duration" key
        }], duration="3600.0")
        tracks = parse_probe_output(probe)
        assert tracks[0]["duration"] == 3600

    def test_invalid_json_returns_empty(self):
        from arm.ripper.ffmpeg import parse_probe_output

        tracks = parse_probe_output("not valid json{{{")
        assert tracks == []

    def test_empty_streams_list(self):
        from arm.ripper.ffmpeg import parse_probe_output

        probe = self._make_probe_json(streams=[], duration="60")
        tracks = parse_probe_output(probe)
        assert len(tracks) == 1
        assert tracks[0]["duration"] == 60


class TestCorrectFfmpegSettings:
    """Test correct_ffmpeg_settings() argument selection."""

    def test_from_job_config(self):
        from arm.ripper.ffmpeg import correct_ffmpeg_settings

        job = unittest.mock.MagicMock()
        job.config.FFMPEG_PRE_FILE_ARGS = "-hwaccel cuda"
        job.config.FFMPEG_POST_FILE_ARGS = "-c:v hevc_nvenc"
        pre, post = correct_ffmpeg_settings(job)
        assert pre == "-hwaccel cuda"
        assert post == "-c:v hevc_nvenc"

    def test_fallback_to_global_config(self):
        from arm.ripper.ffmpeg import correct_ffmpeg_settings
        import arm.config.config as cfg

        job = unittest.mock.MagicMock()
        job.config = None  # no per-job config

        # Set fallback values in global config
        original_pre = cfg.arm_config.get('FFMPEG_PRE_FILE_ARGS')
        original_post = cfg.arm_config.get('FFMPEG_POST_FILE_ARGS')
        cfg.arm_config['FFMPEG_PRE_FILE_ARGS'] = '-global-pre'
        cfg.arm_config['FFMPEG_POST_FILE_ARGS'] = '-global-post'
        try:
            pre, post = correct_ffmpeg_settings(job)
            assert pre == '-global-pre'
            assert post == '-global-post'
        finally:
            # Restore
            if original_pre is not None:
                cfg.arm_config['FFMPEG_PRE_FILE_ARGS'] = original_pre
            else:
                cfg.arm_config.pop('FFMPEG_PRE_FILE_ARGS', None)
            if original_post is not None:
                cfg.arm_config['FFMPEG_POST_FILE_ARGS'] = original_post
            else:
                cfg.arm_config.pop('FFMPEG_POST_FILE_ARGS', None)

    def test_missing_config_attr_uses_global(self):
        from arm.ripper.ffmpeg import correct_ffmpeg_settings
        import arm.config.config as cfg

        job = unittest.mock.MagicMock()
        # config exists but no FFMPEG attrs
        del job.config.FFMPEG_PRE_FILE_ARGS
        del job.config.FFMPEG_POST_FILE_ARGS

        pre, post = correct_ffmpeg_settings(job)
        # getattr with default "" returns "" when attr missing
        assert isinstance(pre, str)
        assert isinstance(post, str)
