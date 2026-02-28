"""Tests for Job model properties and path builders (Phase 2)."""
import os


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

    def test_music(self, sample_job):
        sample_job.video_type = "music"
        assert sample_job.type_subfolder == "music"

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


class TestPatternEngineIntegration:
    """Test that structured fields activate the naming pattern engine."""

    # --- Music ---

    def test_music_formatted_title_uses_pattern(self, sample_job):
        """With artist+album set, formatted_title uses the music title pattern."""
        sample_job.video_type = "music"
        sample_job.artist = "The Beatles"
        sample_job.album = "Abbey Road"
        sample_job.year = "1969"
        assert sample_job.formatted_title == "The Beatles - Abbey Road"

    def test_music_folder_path_uses_pattern(self, sample_job):
        """With artist+album set, build_final_path uses the music folder pattern."""
        sample_job.video_type = "music"
        sample_job.artist = "The Beatles"
        sample_job.album = "Abbey Road"
        sample_job.year = "1969"
        path = sample_job.build_final_path()
        assert path == os.path.join(
            "/home/arm/media/completed", "music",
            "The Beatles", "Abbey Road (1969)"
        )

    def test_music_transcode_path_uses_pattern(self, sample_job):
        sample_job.video_type = "music"
        sample_job.artist = "Pink Floyd"
        sample_job.album = "The Wall"
        sample_job.year = "1979"
        path = sample_job.build_transcode_path()
        assert path == os.path.join(
            "/home/arm/media/transcode", "music",
            "Pink Floyd", "The Wall (1979)"
        )

    def test_music_manual_artist_preferred(self, sample_job):
        """Manual artist overrides auto-detected artist."""
        sample_job.video_type = "music"
        sample_job.artist = "beatles"
        sample_job.artist_manual = "The Beatles"
        sample_job.album = "Help"
        assert sample_job.formatted_title == "The Beatles - Help"

    def test_music_falls_back_without_structured_fields(self, sample_job):
        """Without artist/album, music falls back to Title (Year)."""
        sample_job.video_type = "music"
        sample_job.title = "Pink Floyd The Dark Side of the Moon"
        sample_job.year = "1973"
        assert sample_job.formatted_title == "Pink Floyd The Dark Side of the Moon (1973)"

    # --- Series ---

    def test_series_formatted_title_uses_pattern(self, sample_job):
        """With season+episode set, formatted_title uses the TV title pattern."""
        sample_job.video_type = "series"
        sample_job.title = "Breaking Bad"
        sample_job.season = "1"
        sample_job.episode = "3"
        assert sample_job.formatted_title == "Breaking Bad S01E03"

    def test_series_folder_path_uses_pattern(self, sample_job):
        """With season set, build_final_path uses the TV folder pattern."""
        sample_job.video_type = "series"
        sample_job.title = "Breaking Bad"
        sample_job.season = "2"
        path = sample_job.build_final_path()
        assert path == os.path.join(
            "/home/arm/media/completed", "tv",
            "Breaking Bad", "Season 02"
        )

    def test_series_falls_back_without_season(self, sample_job):
        """Without season/episode, series falls back to Title (Year)."""
        sample_job.video_type = "series"
        sample_job.title = "SERIAL_MOM"
        sample_job.year = "1994"
        assert sample_job.formatted_title == "SERIAL_MOM (1994)"

    def test_series_manual_season_preferred(self, sample_job):
        """Manual season overrides auto-detected season."""
        sample_job.video_type = "series"
        sample_job.title = "Lost"
        sample_job.season = "1"
        sample_job.season_manual = "3"
        sample_job.episode = "5"
        assert sample_job.formatted_title == "Lost S03E05"

    # --- Movies always use pattern (just need title) ---

    def test_movie_still_uses_pattern(self, sample_job):
        """Movies use the pattern engine (default pattern matches old behavior)."""
        sample_job.video_type = "movie"
        sample_job.title = "Inception"
        sample_job.year = "2010"
        assert sample_job.formatted_title == "Inception (2010)"

    # --- Raw path never uses pattern ---

    def test_raw_path_unaffected_by_structured_fields(self, sample_job):
        """build_raw_path always uses title_auto, never the pattern engine."""
        sample_job.video_type = "music"
        sample_job.artist = "The Beatles"
        sample_job.album = "Abbey Road"
        sample_job.title_auto = "Beatles Abbey Road"
        assert sample_job.build_raw_path() == "/home/arm/media/raw/Beatles Abbey Road"


class TestStructuredFieldColumns:
    """Test that the 12 new structured columns exist and are persisted."""

    def test_artist_columns_persist(self, sample_job, app_context):
        from arm.database import db
        sample_job.artist = "Queen"
        sample_job.artist_auto = "Queen"
        sample_job.artist_manual = "Queen (band)"
        db.session.commit()
        db.session.refresh(sample_job)
        assert sample_job.artist == "Queen"
        assert sample_job.artist_auto == "Queen"
        assert sample_job.artist_manual == "Queen (band)"

    def test_album_columns_persist(self, sample_job, app_context):
        from arm.database import db
        sample_job.album = "Jazz"
        sample_job.album_auto = "Jazz"
        sample_job.album_manual = None
        db.session.commit()
        db.session.refresh(sample_job)
        assert sample_job.album == "Jazz"
        assert sample_job.album_auto == "Jazz"
        assert sample_job.album_manual is None

    def test_season_episode_columns_persist(self, sample_job, app_context):
        from arm.database import db
        sample_job.season = "3"
        sample_job.season_auto = "3"
        sample_job.episode = "12"
        sample_job.episode_auto = "12"
        sample_job.episode_manual = "13"
        db.session.commit()
        db.session.refresh(sample_job)
        assert sample_job.season == "3"
        assert sample_job.episode == "12"
        assert sample_job.episode_manual == "13"

    def test_columns_nullable(self, sample_job, app_context):
        """All structured fields default to None."""
        from arm.database import db
        db.session.refresh(sample_job)
        assert sample_job.artist is None
        assert sample_job.album is None
        assert sample_job.season is None
        assert sample_job.episode is None
