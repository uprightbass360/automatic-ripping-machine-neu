"""Tests for Job model properties and path builders (Phase 2)."""


class TestFormattedTitle:
    def test_title_with_year(self, sample_job):
        assert sample_job.formatted_title == "SERIAL_MOM (1994)"

    def test_title_without_year(self, sample_job):
        sample_job.year = ""
        assert sample_job.formatted_title == "SERIAL_MOM"

    def test_manual_title_preferred(self, sample_job):
        sample_job.title_manual = "Serial Mom"
        assert sample_job.formatted_title == "Serial Mom (1994)"

    def test_year_zero_excluded(self, sample_job):
        sample_job.year = "0000"
        assert sample_job.formatted_title == "SERIAL_MOM"

    def test_year_none_excluded(self, sample_job):
        sample_job.year = None
        assert sample_job.formatted_title == "SERIAL_MOM"


class TestTypeSubfolder:
    def test_movie(self, sample_job):
        assert sample_job.type_subfolder == "movies"

    def test_series(self, sample_job):
        sample_job.video_type = "series"
        assert sample_job.type_subfolder == "tv"

    def test_unknown(self, sample_job):
        sample_job.video_type = "unknown"
        assert sample_job.type_subfolder == "unidentified"


class TestBuildPaths:
    def test_build_raw_path(self, sample_job):
        assert sample_job.build_raw_path() == "/home/arm/media/raw/SERIAL_MOM"

    def test_build_transcode_path(self, sample_job):
        assert sample_job.build_transcode_path() == "/home/arm/media/transcode/movies/SERIAL_MOM (1994)"

    def test_build_final_path(self, sample_job):
        assert sample_job.build_final_path() == "/home/arm/media/completed/movies/SERIAL_MOM (1994)"

    def test_build_raw_path_uses_title_auto(self, sample_job):
        """raw_path should use title_auto, not title (which may be corrected)."""
        sample_job.title = "Serial Mom"
        sample_job.title_auto = "SERIAL_MOM"
        assert sample_job.build_raw_path() == "/home/arm/media/raw/SERIAL_MOM"

    def test_build_paths_with_manual_title(self, sample_job):
        sample_job.title_manual = "Serial Mom"
        # raw_path uses title_auto (original auto-detected title)
        assert sample_job.build_raw_path() == "/home/arm/media/raw/SERIAL_MOM"
        # transcode and final use formatted_title (prefers manual)
        assert sample_job.build_transcode_path() == "/home/arm/media/transcode/movies/Serial Mom (1994)"
        assert sample_job.build_final_path() == "/home/arm/media/completed/movies/Serial Mom (1994)"

    def test_build_paths_series(self, sample_job):
        sample_job.video_type = "series"
        assert sample_job.build_transcode_path() == "/home/arm/media/transcode/tv/SERIAL_MOM (1994)"
        assert sample_job.build_final_path() == "/home/arm/media/completed/tv/SERIAL_MOM (1994)"
