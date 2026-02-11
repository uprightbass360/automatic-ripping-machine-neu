"""Tests for disc identification — README Feature: Video Metadata Retrieval.

Covers identify.py functions: find_mount(), identify_bluray(), update_job(),
metadata_selector(), identify_loop(), try_with_year(), try_without_year().
Also covers arm/ui/metadata.py: call_omdb_api() fallback for short titles.
"""
import json
import subprocess
import unittest.mock

import pytest


class TestFindMount:
    """Test find_mount() parsing of findmnt JSON output."""

    def test_returns_mountpoint(self, tmp_path):
        """Returns the target from findmnt JSON when accessible."""
        from arm.ripper.identify import find_mount

        mount_target = str(tmp_path)
        findmnt_output = json.dumps({
            "filesystems": [{"target": mount_target, "source": "/dev/sr0"}]
        })
        with unittest.mock.patch('arm.ripper.identify.arm_subprocess', return_value=findmnt_output):
            result = find_mount('/dev/sr0')
        assert result == mount_target

    def test_returns_none_when_no_output(self):
        """Returns None when findmnt produces no output."""
        from arm.ripper.identify import find_mount

        with unittest.mock.patch('arm.ripper.identify.arm_subprocess', return_value=None):
            result = find_mount('/dev/sr0')
        assert result is None

    def test_skips_inaccessible_mountpoint(self, tmp_path):
        """Skips mountpoints that aren't readable."""
        from arm.ripper.identify import find_mount

        findmnt_output = json.dumps({
            "filesystems": [{"target": "/nonexistent/path", "source": "/dev/sr0"}]
        })
        with unittest.mock.patch('arm.ripper.identify.arm_subprocess', return_value=findmnt_output):
            result = find_mount('/dev/sr0')
        assert result is None

    def test_multiple_mountpoints_returns_first_accessible(self, tmp_path):
        """Returns first accessible mountpoint from multiple entries."""
        from arm.ripper.identify import find_mount

        findmnt_output = json.dumps({
            "filesystems": [
                {"target": "/nonexistent", "source": "/dev/sr0"},
                {"target": str(tmp_path), "source": "/dev/sr0"},
            ]
        })
        with unittest.mock.patch('arm.ripper.identify.arm_subprocess', return_value=findmnt_output):
            result = find_mount('/dev/sr0')
        assert result == str(tmp_path)


class TestCheckMount:
    """Test check_mount() mount-or-find logic."""

    def test_already_mounted(self, tmp_path):
        """If disc is already mounted, returns True and sets mountpoint."""
        from arm.ripper.identify import check_mount

        job = unittest.mock.MagicMock()
        job.devpath = '/dev/sr0'
        with unittest.mock.patch('arm.ripper.identify.find_mount', return_value=str(tmp_path)):
            result = check_mount(job)
        assert result is True
        assert job.mountpoint == str(tmp_path)

    def test_mount_attempt_succeeds(self, tmp_path):
        """If not mounted, tries mount and succeeds on second find_mount call."""
        from arm.ripper.identify import check_mount

        job = unittest.mock.MagicMock()
        job.devpath = '/dev/sr0'
        # First call: not mounted; second call after mount: found
        with unittest.mock.patch('arm.ripper.identify.find_mount',
                                 side_effect=[None, str(tmp_path)]), \
             unittest.mock.patch('arm.ripper.identify.arm_subprocess'):
            result = check_mount(job)
        assert result is True

    def test_mount_fails(self):
        """If mount fails, returns False."""
        from arm.ripper.identify import check_mount

        job = unittest.mock.MagicMock()
        job.devpath = '/dev/sr0'
        with unittest.mock.patch('arm.ripper.identify.find_mount', return_value=None), \
             unittest.mock.patch('arm.ripper.identify.arm_subprocess'):
            result = check_mount(job)
        assert result is False


class TestIdentifyBluray:
    """Test identify_bluray() XML parsing for Blu-ray discs."""

    def _make_job(self):
        """Create a minimal mock job for bluray identification."""
        from arm.models.job import Job
        with unittest.mock.patch.object(Job, 'parse_udev'), \
             unittest.mock.patch.object(Job, 'get_pid'):
            job = Job('/dev/sr0')
        job.disctype = 'bluray'
        job.label = 'SERIAL_MOM'
        job.title = None
        job.title_auto = None
        job.year = None
        job.year_auto = None
        return job

    def test_parses_xml_title(self, app_context, tmp_path):
        """Extracts title from bdmt_eng.xml."""
        from arm.ripper.identify import identify_bluray

        job = self._make_job()
        job.mountpoint = str(tmp_path)

        # Create bdmt_eng.xml structure
        xml_dir = tmp_path / 'BDMV' / 'META' / 'DL'
        xml_dir.mkdir(parents=True)
        xml_file = xml_dir / 'bdmt_eng.xml'
        xml_file.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<disclib xmlns:di="urn:BDA:bdmv;discinfo">'
            '<di:discinfo><di:title><di:name>Serial Mom</di:name></di:title></di:discinfo>'
            '</disclib>'
        )

        result = identify_bluray(job)
        assert result is True
        assert 'Serial-Mom' in job.title or 'Serial Mom' in job.title

    def test_xml_missing_falls_back_to_label(self, app_context, tmp_path):
        """When bdmt_eng.xml is missing, uses disc label as title."""
        from arm.ripper.identify import identify_bluray

        job = self._make_job()
        job.mountpoint = str(tmp_path)
        # No XML file exists

        result = identify_bluray(job)
        assert result is True
        assert job.title is not None
        # Should use label "SERIAL_MOM", cleaned up
        assert 'Serial' in job.title or 'SERIAL' in job.title

    def test_xml_missing_empty_label(self, app_context, tmp_path):
        """When XML is missing AND label is empty, returns False."""
        from arm.ripper.identify import identify_bluray

        job = self._make_job()
        job.mountpoint = str(tmp_path)
        job.label = ""

        result = identify_bluray(job)
        assert result is False

    def test_strips_bluray_tm_suffix(self, app_context, tmp_path):
        """Strips ' - Blu-rayTM' from extracted title."""
        from arm.ripper.identify import identify_bluray

        job = self._make_job()
        job.mountpoint = str(tmp_path)

        xml_dir = tmp_path / 'BDMV' / 'META' / 'DL'
        xml_dir.mkdir(parents=True)
        xml_file = xml_dir / 'bdmt_eng.xml'
        xml_file.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<disclib xmlns:di="urn:BDA:bdmv;discinfo">'
            '<di:discinfo><di:title><di:name>Serial Mom - Blu-rayTM</di:name></di:title></di:discinfo>'
            '</disclib>'
        )

        identify_bluray(job)
        assert 'Blu-ray' not in job.title
        assert 'Serial' in job.title


class TestUpdateJob:
    """Test update_job() search result processing."""

    def test_valid_search_results(self, app_context, sample_job):
        """Valid OMDb-format search results update the job."""
        from arm.ripper.identify import update_job

        search_results = {
            'Search': [{
                'Title': 'Serial Mom',
                'Year': '1994',
                'Type': 'movie',
                'imdbID': 'tt0111127',
                'Poster': 'https://example.com/poster.jpg',
            }]
        }
        result = update_job(sample_job, search_results)
        assert result is True
        assert 'Serial-Mom' in sample_job.title or 'Serial Mom' in sample_job.title
        assert sample_job.year == '1994'
        assert sample_job.video_type == 'movie'
        assert sample_job.imdb_id == 'tt0111127'
        assert sample_job.hasnicetitle is True

    def test_no_search_key_returns_none(self, app_context, sample_job):
        """Missing 'Search' key returns None."""
        from arm.ripper.identify import update_job

        result = update_job(sample_job, {'Response': 'False', 'Error': 'Not found'})
        assert result is None

    def test_empty_search_list(self, app_context, sample_job):
        """Empty 'Search' list raises IndexError (expected — caller catches)."""
        from arm.ripper.identify import update_job

        with pytest.raises(IndexError):
            update_job(sample_job, {'Search': []})


class TestMetadataSelector:
    """Test metadata_selector() provider switching."""

    def _make_job(self):
        from arm.models.job import Job
        with unittest.mock.patch.object(Job, 'parse_udev'), \
             unittest.mock.patch.object(Job, 'get_pid'):
            job = Job('/dev/sr0')
        job.title = 'TEST'
        job.label = 'TEST'
        return job

    def test_omdb_provider(self):
        """When METADATA_PROVIDER=omdb, calls call_omdb_api."""
        from arm.ripper.identify import metadata_selector
        import arm.config.config as cfg

        job = self._make_job()
        original = cfg.arm_config.get('METADATA_PROVIDER')
        cfg.arm_config['METADATA_PROVIDER'] = 'omdb'
        try:
            # Return None to avoid update_job being called
            with unittest.mock.patch('arm.ripper.identify.ui_utils.call_omdb_api',
                                     return_value=None) as mock_omdb:
                metadata_selector(job, 'Serial Mom', '1994')
                mock_omdb.assert_called_once()
        finally:
            if original is not None:
                cfg.arm_config['METADATA_PROVIDER'] = original

    def test_tmdb_provider(self):
        """When METADATA_PROVIDER=tmdb, calls tmdb_search."""
        from arm.ripper.identify import metadata_selector
        import arm.config.config as cfg

        job = self._make_job()
        original = cfg.arm_config.get('METADATA_PROVIDER')
        cfg.arm_config['METADATA_PROVIDER'] = 'tmdb'
        try:
            with unittest.mock.patch('arm.ripper.identify.ui_utils.tmdb_search',
                                     return_value=None) as mock_tmdb:
                metadata_selector(job, 'Serial Mom', '1994')
                mock_tmdb.assert_called_once()
        finally:
            if original is not None:
                cfg.arm_config['METADATA_PROVIDER'] = original

    def test_unknown_provider_returns_none(self):
        """Unknown METADATA_PROVIDER returns None."""
        from arm.ripper.identify import metadata_selector
        import arm.config.config as cfg

        job = self._make_job()
        original = cfg.arm_config.get('METADATA_PROVIDER')
        cfg.arm_config['METADATA_PROVIDER'] = 'invalid_provider'
        try:
            result = metadata_selector(job, 'Serial Mom', '1994')
            assert result is None
        finally:
            if original is not None:
                cfg.arm_config['METADATA_PROVIDER'] = original


class TestTryWithYear:
    """Test try_with_year() metadata retry with year variations."""

    def test_returns_existing_response(self):
        """If response is already set, returns it unchanged."""
        from arm.ripper.identify import try_with_year

        existing = {'Search': [{'Title': 'Test'}]}
        result = try_with_year(None, existing, 'Test', '2020')
        assert result is existing

    def test_tries_with_year(self):
        """When response is None and year given, calls metadata_selector."""
        from arm.ripper.identify import try_with_year

        mock_result = {'Search': [{'Title': 'Test'}]}
        with unittest.mock.patch('arm.ripper.identify.metadata_selector',
                                 return_value=mock_result) as mock_ms:
            result = try_with_year(None, None, 'Test', '2020')
            assert result == mock_result
            mock_ms.assert_called_once_with(None, 'Test', '2020')

    def test_subtracts_year_on_failure(self):
        """If first try fails, subtracts 1 year and tries again."""
        from arm.ripper.identify import try_with_year

        mock_result = {'Search': [{'Title': 'Test'}]}
        with unittest.mock.patch('arm.ripper.identify.metadata_selector',
                                 side_effect=[None, mock_result]) as mock_ms:
            result = try_with_year(None, None, 'Test', '2020')
            assert result == mock_result
            assert mock_ms.call_count == 2
            # Second call with year-1
            assert mock_ms.call_args_list[1][0][2] == '2019'

    def test_no_year_skips(self):
        """If year is falsy, skips metadata_selector call."""
        from arm.ripper.identify import try_with_year

        with unittest.mock.patch('arm.ripper.identify.metadata_selector') as mock_ms:
            result = try_with_year(None, None, 'Test', None)
            mock_ms.assert_not_called()
            assert result is None


class TestTryWithoutYear:
    """Test try_without_year() metadata retry without year."""

    def test_calls_when_response_none(self):
        """Calls metadata_selector without year when response is None."""
        from arm.ripper.identify import try_without_year

        mock_result = {'Search': [{'Title': 'Test'}]}
        with unittest.mock.patch('arm.ripper.identify.metadata_selector',
                                 return_value=mock_result) as mock_ms:
            result = try_without_year(None, None, 'Test')
            mock_ms.assert_called_once_with(None, 'Test')
            assert result == mock_result

    def test_skips_when_response_exists(self):
        """Does nothing when response already has a value."""
        from arm.ripper.identify import try_without_year

        existing = {'Search': [{'Title': 'Existing'}]}
        with unittest.mock.patch('arm.ripper.identify.metadata_selector') as mock_ms:
            result = try_without_year(None, existing, 'Test')
            mock_ms.assert_not_called()
            assert result is existing


class TestIdentifyLoop:
    """Test identify_loop() progressive title slicing retry logic."""

    def test_with_existing_response_does_nothing(self):
        """When response is provided, no metadata_selector calls are made."""
        from arm.ripper.identify import identify_loop

        existing = {'Search': [{'Title': 'Test'}]}
        with unittest.mock.patch('arm.ripper.identify.metadata_selector'), \
             unittest.mock.patch('arm.ripper.identify.try_with_year', return_value=existing), \
             unittest.mock.patch('arm.ripper.identify.try_without_year', return_value=existing):
            identify_loop(None, existing, 'Test', '2020')
            # When response is not None, the function should return early

    def test_slices_title_on_hyphen(self):
        """When response is None, tries slicing title on hyphens."""
        from arm.ripper.identify import identify_loop

        call_count = 0
        titles_tried = []

        def mock_selector(job, title, year=None):
            nonlocal call_count
            titles_tried.append(title)
            call_count += 1
            if call_count >= 2:
                return {'Search': [{'Title': 'Found'}]}
            return None

        with unittest.mock.patch('arm.ripper.identify.metadata_selector',
                                 side_effect=mock_selector), \
             unittest.mock.patch('arm.ripper.identify.try_with_year', return_value=None), \
             unittest.mock.patch('arm.ripper.identify.try_without_year', return_value=None):
            identify_loop(None, None, 'Title-Part-Extra', '2020')
        # Should have tried "Title-Part" (sliced off "-Extra")
        assert any('Title-Part' in t for t in titles_tried)

    def test_slices_title_on_plus(self):
        """When hyphens exhausted, tries slicing on plus signs."""
        from arm.ripper.identify import identify_loop

        titles_tried = []

        def mock_selector(job, title, year=None):
            titles_tried.append(title)
            # Return None for first several tries, then succeed
            if title == 'Title':
                return {'Search': [{'Title': 'Found'}]}
            return None

        with unittest.mock.patch('arm.ripper.identify.metadata_selector',
                                 side_effect=mock_selector), \
             unittest.mock.patch('arm.ripper.identify.try_with_year', return_value=None), \
             unittest.mock.patch('arm.ripper.identify.try_without_year', return_value=None):
            identify_loop(None, None, 'Title+Extra+Words', '2020')
        # Should eventually try 'Title' (sliced off '+Extra+Words')
        assert 'Title' in titles_tried


class TestMalformedBlurayXml:
    """Test identify_bluray() handles malformed XML gracefully (#1650)."""

    def _make_job(self):
        from arm.models.job import Job
        with unittest.mock.patch.object(Job, 'parse_udev'), \
             unittest.mock.patch.object(Job, 'get_pid'):
            job = Job('/dev/sr0')
        job.disctype = 'bluray'
        job.label = 'SERIAL_MOM'
        job.title = None
        job.title_auto = None
        job.year = None
        job.year_auto = None
        return job

    def test_malformed_xml_falls_back_to_label(self, app_context, tmp_path):
        """Malformed XML should trigger label fallback, not crash."""
        from arm.ripper.identify import identify_bluray

        job = self._make_job()
        job.mountpoint = str(tmp_path)

        xml_dir = tmp_path / 'BDMV' / 'META' / 'DL'
        xml_dir.mkdir(parents=True)
        xml_file = xml_dir / 'bdmt_eng.xml'
        xml_file.write_text('<<<not valid xml>>>')

        result = identify_bluray(job)
        assert result is True
        assert 'Serial Mom' in job.title

    def test_malformed_xml_empty_label(self, app_context, tmp_path):
        """Malformed XML with empty label returns False."""
        from arm.ripper.identify import identify_bluray

        job = self._make_job()
        job.mountpoint = str(tmp_path)
        job.label = ""

        xml_dir = tmp_path / 'BDMV' / 'META' / 'DL'
        xml_dir.mkdir(parents=True)
        xml_file = xml_dir / 'bdmt_eng.xml'
        xml_file.write_text('<<<not valid xml>>>')

        result = identify_bluray(job)
        assert result is False

    def test_none_label_does_not_produce_string_none(self, app_context, tmp_path):
        """When label is None and XML is malformed, title must NOT become 'None'."""
        from arm.ripper.identify import identify_bluray

        job = self._make_job()
        job.mountpoint = str(tmp_path)
        job.label = None

        xml_dir = tmp_path / 'BDMV' / 'META' / 'DL'
        xml_dir.mkdir(parents=True)
        xml_file = xml_dir / 'bdmt_eng.xml'
        xml_file.write_text('<<<not valid xml>>>')

        result = identify_bluray(job)
        assert result is False
        # Must be empty string, not the literal string "None"
        assert job.title != "None"
        assert job.title == ""

    def test_truncated_xml_falls_back(self, app_context, tmp_path):
        """Truncated/incomplete XML should trigger label fallback."""
        from arm.ripper.identify import identify_bluray

        job = self._make_job()
        job.mountpoint = str(tmp_path)

        xml_dir = tmp_path / 'BDMV' / 'META' / 'DL'
        xml_dir.mkdir(parents=True)
        xml_file = xml_dir / 'bdmt_eng.xml'
        xml_file.write_bytes(b'<?xml version="1.0"?><disclib><di:discinfo')  # truncated

        result = identify_bluray(job)
        assert result is True
        assert 'Serial Mom' in job.title


class TestIdentifyUnmount:
    """Test identify() always unmounts the disc (#1664)."""

    def test_umount_called_on_success(self):
        """umount is called after successful identification."""
        from arm.ripper.identify import identify

        job = unittest.mock.MagicMock()
        job.devpath = '/dev/sr0'
        job.disctype = 'music'  # skip video identification

        with unittest.mock.patch('arm.ripper.identify.check_mount', return_value=True), \
             unittest.mock.patch('arm.ripper.identify.subprocess.run') as mock_run:
            identify(job)
            mock_run.assert_called_once_with(
                ["umount", "/dev/sr0"], stderr=subprocess.PIPE, text=True
            )

    def test_umount_called_on_exception(self):
        """umount is called even when identification raises an exception."""
        from arm.ripper.identify import identify

        job = unittest.mock.MagicMock()
        job.devpath = '/dev/sr0'
        job.disctype = 'bluray'

        with unittest.mock.patch('arm.ripper.identify.check_mount', return_value=True), \
             unittest.mock.patch('arm.ripper.identify.cfg') as mock_cfg, \
             unittest.mock.patch('arm.ripper.identify.subprocess.run') as mock_run:
            mock_cfg.arm_config = {"GET_VIDEO_TITLE": True}
            # identify_bluray will fail because job is a MagicMock without a real mountpoint
            with unittest.mock.patch('arm.ripper.identify.identify_bluray',
                                     side_effect=RuntimeError("test error")):
                with pytest.raises(RuntimeError):
                    identify(job)
            # umount should still have been called
            mock_run.assert_called_once_with(
                ["umount", "/dev/sr0"], stderr=subprocess.PIPE, text=True
            )

    def test_umount_called_when_not_mounted(self):
        """umount is called even if disc was not successfully mounted."""
        from arm.ripper.identify import identify

        job = unittest.mock.MagicMock()
        job.devpath = '/dev/sr0'
        job.disctype = 'data'

        with unittest.mock.patch('arm.ripper.identify.check_mount', return_value=False), \
             unittest.mock.patch('arm.ripper.identify.subprocess.run') as mock_run:
            identify(job)
            mock_run.assert_called_once()


class TestOmdbShortTitleFallback:
    """Test call_omdb_api() fallback to ?t= for short/numeric titles (#1430)."""

    def _mock_urlopen(self, responses):
        """Create a mock urlopen that returns different responses per call."""
        call_count = [0]

        def side_effect(url, **kwargs):
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            mock_resp = unittest.mock.MagicMock()
            mock_resp.read.return_value = json.dumps(responses[idx]).encode()
            return mock_resp

        return side_effect

    @unittest.mock.patch.dict('arm.config.config.arm_config', {'OMDB_API_KEY': 'test_key'})
    def test_search_failure_falls_back_to_exact_title(self):
        """When ?s= returns 'Too many results', ?t= is tried."""
        from arm.ui.metadata import call_omdb_api

        search_error = {"Response": "False", "Error": "Too many results."}
        exact_match = {
            "Response": "True",
            "Title": "9",
            "Year": "2009",
            "Type": "movie",
            "imdbID": "tt0472033",
            "Poster": "https://example.com/9.jpg",
        }
        mock_open = self._mock_urlopen([search_error, exact_match])
        with unittest.mock.patch('arm.ui.metadata.urllib.request.urlopen', side_effect=mock_open):
            result = call_omdb_api(title="9", year="2009")

        assert result is not None
        assert result['Search'][0]['Title'] == '9'
        assert result['Search'][0]['imdbID'] == 'tt0472033'

    @unittest.mock.patch.dict('arm.config.config.arm_config', {'OMDB_API_KEY': 'test_key'})
    def test_both_search_and_exact_fail_returns_none(self):
        """When both ?s= and ?t= fail, returns None."""
        from arm.ui.metadata import call_omdb_api

        error_resp = {"Response": "False", "Error": "Movie not found!"}
        mock_open = self._mock_urlopen([error_resp, error_resp])
        with unittest.mock.patch('arm.ui.metadata.urllib.request.urlopen', side_effect=mock_open):
            result = call_omdb_api(title="xyznonexistent", year="2020")

        assert result is None

    @unittest.mock.patch.dict('arm.config.config.arm_config', {'OMDB_API_KEY': 'test_key'})
    def test_search_succeeds_no_fallback_needed(self):
        """When ?s= succeeds, no fallback is triggered."""
        from arm.ui.metadata import call_omdb_api

        search_success = {
            "Response": "True",
            "Search": [{"Title": "The Matrix", "Year": "1999", "imdbID": "tt0133093",
                        "Type": "movie", "Poster": "https://example.com/matrix.jpg"}]
        }
        mock_open = self._mock_urlopen([search_success])
        with unittest.mock.patch('arm.ui.metadata.urllib.request.urlopen', side_effect=mock_open):
            result = call_omdb_api(title="The Matrix", year="1999")

        assert result is not None
        assert result['Search'][0]['Title'] == 'The Matrix'

    @unittest.mock.patch.dict('arm.config.config.arm_config', {'OMDB_API_KEY': 'test_key'})
    def test_fallback_network_error_returns_none(self):
        """When ?s= fails and ?t= raises a network error, returns None gracefully (#1430)."""
        from arm.ui.metadata import call_omdb_api

        call_count = [0]

        def mock_urlopen(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (?s=) returns error response
                mock_resp = unittest.mock.MagicMock()
                mock_resp.read.return_value = json.dumps(
                    {"Response": "False", "Error": "Too many results."}
                ).encode()
                return mock_resp
            # Second call (?t=) raises network error
            raise urllib.error.URLError("DNS lookup failed")

        import urllib.error
        with unittest.mock.patch('arm.ui.metadata.urllib.request.urlopen',
                                 side_effect=mock_urlopen):
            result = call_omdb_api(title="9", year="2009")

        assert result is None
