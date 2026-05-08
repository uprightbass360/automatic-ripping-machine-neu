import logging
import os
import psutil
import pyudev
import time
import uuid

from datetime import datetime as dt
from prettytable import PrettyTable
from sqlalchemy.ext.hybrid import hybrid_property

from arm.ripper import music_brainz
from arm.database import db
import arm.config.config as cfg

# THESE IMPORTS ARE REQUIRED FOR THE db.Relationships to work
from arm.models.track import Track  # noqa: F401
from arm.models.config import Config  # noqa: F401


def _listdir_safe(path):
    """List a directory, returning [] on any OSError (stale handle, missing, etc.)."""
    try:
        return os.listdir(path)
    except OSError:
        return []


def _find_disc_dir(mountpoint, name):
    """Case-insensitive lookup of a top-level entry on the mount.

    Returns the actual on-disk name (so the caller can join the path) or
    None. Using os.listdir() instead of os.path.isdir() avoids os.stat()
    on the directory entry, which fails with "stale file handle" on some
    burned UDF DVD-Rs even though the kernel still lists the entry. See
    upstream issue #1746 / PR #1747.
    """
    target = name.lower()
    for entry in _listdir_safe(mountpoint):
        if entry.lower() == target:
            return entry
    return None


def _disc_dir_exists(mountpoint, name):
    """True if a case-insensitive directory entry exists at the mount root."""
    return _find_disc_dir(mountpoint, name) is not None


# JobState lives in shared contracts so transcoder + arm-ui can import the
# same enum that arm-neu persists. Re-exported here for backwards
# compatibility with any existing `from arm.models.job import JobState`.
from arm_contracts.enums import JobState, SourceType  # noqa: E402,F401


JOB_STATUS_FINISHED = {
    JobState.SUCCESS,
    JobState.FAILURE,
}
JOB_STATUS_SCANNING = {
    JobState.IDENTIFYING,
}
JOB_STATUS_RIPPING = {
    JobState.AUDIO_RIPPING,
    JobState.VIDEO_RIPPING,
    JobState.MANUAL_PAUSED,
    JobState.MAKEMKV_THROTTLED,
    JobState.VIDEO_INFO,
    JobState.COPYING,
    JobState.EJECTING,
}
JOB_STATUS_TRANSCODING = {
    JobState.TRANSCODE_ACTIVE,
    JobState.TRANSCODE_WAITING,
}


class Job(db.Model):
    """
    Job Class hold most of the details for each job
    connects to track, config
    """
    job_id = db.Column(db.Integer, primary_key=True)
    arm_version = db.Column(db.String(20))
    crc_id = db.Column(db.String(63))
    logfile = db.Column(db.String(256))
    start_time = db.Column(db.DateTime)
    stop_time = db.Column(db.DateTime)
    job_length = db.Column(db.String(12))
    status = db.Column(
        db.Enum(JobState, name="job_state_enum",
                native_enum=False, validate_strings=True,
                values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    stage = db.Column(db.String(63))
    no_of_titles = db.Column(db.Integer)
    title = db.Column(db.String(256))
    title_auto = db.Column(db.String(256))
    title_manual = db.Column(db.String(256))
    year = db.Column(db.String(4))
    year_auto = db.Column(db.String(4))
    year_manual = db.Column(db.String(4))
    video_type = db.Column(db.String(20))
    video_type_auto = db.Column(db.String(20))
    video_type_manual = db.Column(db.String(20))
    imdb_id = db.Column(db.String(15))
    imdb_id_auto = db.Column(db.String(15))
    imdb_id_manual = db.Column(db.String(15))
    poster_url = db.Column(db.String(256))
    poster_url_auto = db.Column(db.String(256))
    poster_url_manual = db.Column(db.String(256))
    devpath = db.Column(db.String(15))
    mountpoint = db.Column(db.String(20))
    hasnicetitle = db.Column(db.Boolean)
    errors = db.Column(db.Text)
    disctype = db.Column(db.String(20))  # dvd/bluray/bluray4k/data/music/unknown
    label = db.Column(db.String(256))
    path = db.Column(db.String(256))
    raw_path = db.Column(db.String(256))
    transcode_path = db.Column(db.String(256))
    # Music structured fields
    artist = db.Column(db.String(256))
    artist_auto = db.Column(db.String(256))
    artist_manual = db.Column(db.String(256))
    album = db.Column(db.String(256))
    album_auto = db.Column(db.String(256))
    album_manual = db.Column(db.String(256))
    # TV structured fields
    season = db.Column(db.String(10))
    season_auto = db.Column(db.String(10))
    season_manual = db.Column(db.String(10))
    episode = db.Column(db.String(10))
    episode_auto = db.Column(db.String(10))
    episode_manual = db.Column(db.String(10))
    transcode_overrides = db.Column(db.Text, nullable=True)  # JSON dict of per-job transcode settings
    multi_title = db.Column(db.Boolean, default=False)
    disc_number = db.Column(db.Integer, nullable=True)
    disc_total = db.Column(db.Integer, nullable=True)
    tvdb_id = db.Column(db.Integer, nullable=True)
    guid = db.Column(db.String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    ejected = db.Column(db.Boolean)
    updated = db.Column(db.Boolean)
    pid = db.Column(db.Integer)
    pid_hash = db.Column(db.Integer)
    is_iso = db.Column(db.Boolean)
    source_type = db.Column(
        db.Enum(SourceType, name="job_source_type_enum",
                native_enum=False, validate_strings=True,
                values_callable=lambda e: [m.value for m in e]),
        default=SourceType.disc.value,
        server_default=SourceType.disc.value,
        nullable=False,
    )
    source_path = db.Column(db.String(1024), nullable=True)
    manual_start = db.Column(db.Boolean)
    manual_pause = db.Column(db.Boolean)
    manual_mode = db.Column(db.Boolean)
    wait_start_time = db.Column(db.DateTime, nullable=True)
    title_pattern_override = db.Column(db.String(512), nullable=True)
    folder_pattern_override = db.Column(db.String(512), nullable=True)
    tracks = db.relationship('Track', backref='job', lazy='dynamic')
    config = db.relationship('Config', uselist=False, backref="job")
    expected_titles = db.relationship(
        "ExpectedTitle",
        backref="job",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __init__(self, devpath, _skip_hardware=False):
        """Return a disc object"""
        self.devpath = devpath
        self.guid = str(uuid.uuid4())
        self.mountpoint = ""
        self.hasnicetitle = False
        self.video_type = "unknown"
        self.ejected = False
        self.updated = False
        # Status starts in IDENTIFYING - the disc-identification phase is
        # the first thing the ripper does after Job() construction.
        # Production code overwrites this almost immediately via
        # database_updater(); the default is here so the NOT NULL
        # constraint on Job.status is satisfied even on bare Job() use
        # (e.g. from test fixtures that bypass the rip orchestration).
        self.status = JobState.IDENTIFYING.value
        if cfg.arm_config.get('VIDEOTYPE', 'auto') != "auto":
            self.video_type = cfg.arm_config['VIDEOTYPE']
        if not _skip_hardware:
            self.parse_udev()
            self.get_pid()
        self.stage = ""
        self.manual_start = False
        self.manual_pause = False
        self.manual_mode = False
        self.has_track_99 = False

    @classmethod
    def from_folder(cls, source_path: str, disctype: str):
        """Create a Job from a folder path, bypassing udev/drive detection."""
        job = cls(
            devpath=None,
            _skip_hardware=True,
        )
        job.source_type = SourceType.folder.value
        job.source_path = source_path
        job.disctype = disctype
        job.start_time = dt.now()
        job.is_iso = False
        if cfg.arm_config.get('VIDEOTYPE', 'auto') != "auto":
            job.video_type = cfg.arm_config['VIDEOTYPE']
        return job

    @classmethod
    def from_iso(cls, source_path: str, disctype: str):
        """Create a Job from an ISO file path, bypassing udev/drive detection."""
        job = cls(
            devpath=None,
            _skip_hardware=True,
        )
        job.source_type = SourceType.iso.value
        job.source_path = source_path
        job.disctype = disctype
        job.start_time = dt.now()
        job.is_iso = True
        if cfg.arm_config.get('VIDEOTYPE', 'auto') != "auto":
            job.video_type = cfg.arm_config['VIDEOTYPE']
        return job

    def __str__(self):
        """Returns a string of the object"""

        return_string = self.__class__.__name__ + ": "
        for attr, value in self.__dict__.items():
            return_string = return_string + "(" + str(attr) + "=" + str(value) + ") "

        return return_string

    def __repr__(self):
        return f'<Job {self.label}>'

    def parse_udev(self):
        """Parse udev for properties of current disc"""
        context = pyudev.Context()
        device = pyudev.Devices.from_device_file(context, self.devpath)
        self.disctype = "unknown"

        for key, value in device.items():
            logging.debug(f"pyudev: {key}: {value}")
            if key == "ID_FS_LABEL":
                self.label = value
                if value == "iso9660":
                    self.disctype = "data"
            elif key == "ID_CDROM_MEDIA_BD":
                self.disctype = "bluray"
            elif key == "ID_CDROM_MEDIA_DVD":
                self.disctype = "dvd"
            elif key == "ID_CDROM_MEDIA_TRACK_COUNT_AUDIO":
                self.disctype = "music"
            else:
                continue

    def get_pid(self):
        """
        Get the jobs process id
        :return: None
        """
        pid = os.getpid()
        process_id = psutil.Process(pid)
        self.pid = pid
        self.pid_hash = hash(process_id)

    def get_disc_type(self, found_hvdvd_ts):
        """
        Checks/corrects the current disc-type
        :param found_hvdvd_ts:  gets pushed in from utils - saves importing utils
        :return: None
        """
        if self.disctype == "music":
            logging.debug("Disc is music.")
            self.label = music_brainz.main(self)
        elif (audio_ts := _find_disc_dir(self.mountpoint, "AUDIO_TS")) \
                and _listdir_safe(os.path.join(self.mountpoint, audio_ts)):
            logging.debug(f"Found: {self.mountpoint}/{audio_ts}")
            self.disctype = "data"
        elif _disc_dir_exists(self.mountpoint, "VIDEO_TS"):
            logging.debug(f"Found: {self.mountpoint}/VIDEO_TS")
            self.disctype = "dvd"
        elif (bdmv := _find_disc_dir(self.mountpoint, "BDMV")):
            logging.debug(f"Found: {self.mountpoint}/{bdmv}")
            # Detect UHD by reading the index.bdmv header version.
            # INDX0300 = UHD (AACS2), INDX0200 = standard Blu-ray.
            # The old check (/CERTIFICATE/id.bdmv) is unreliable - that
            # file exists on most standard Blu-rays with BD-J content.
            index_path = os.path.join(self.mountpoint, bdmv, "index.bdmv")
            try:
                with open(index_path, "rb") as f:
                    header = f.read(8)
                if header == b"INDX0300":
                    logging.debug("index.bdmv header is INDX0300 — UHD Blu-ray")
                    self.disctype = "bluray4k"
                else:
                    logging.debug(f"index.bdmv header is {header!r} — standard Blu-ray")
                    self.disctype = "bluray"
            except OSError:
                logging.debug("Could not read index.bdmv — assuming standard Blu-ray")
                self.disctype = "bluray"
        elif _disc_dir_exists(self.mountpoint, "HVDVD_TS"):
            logging.debug(f"Found: {self.mountpoint}/HVDVD_TS")
            # do something here
        elif found_hvdvd_ts:
            logging.debug("Found file: HVDVD_TS")
            # do something here too
        else:
            logging.debug("Did not find valid dvd/bd files. Changing disc-type to 'data'")
            self.disctype = "data"

    def identify_audio_cd(self):
        """
        Get the title for audio cds to use for the logfile name.

        Needs the job class passed into it so it can be forwarded to mb

        return - only the logfile - setup_logging() adds the full path
        """
        # Use the music label if we can find it - defaults to music_cd.log
        disc_id = music_brainz.get_disc_id(self)
        logging.debug(f"music_id: {disc_id}")

        # Create placeholder tracks from the disc TOC so the UI can
        # display track durations during the manual-wait period.
        music_brainz.create_toc_tracks(self, disc_id)

        mb_title = music_brainz.get_title(disc_id, self)
        logging.debug(f"mm_title: {mb_title}")

        if mb_title == "not identified":
            self.label = self.title = mb_title
            return "music_cd"
        else:
            return mb_title

    def pretty_table(self):
        """Returns a string of the prettytable"""
        pretty_table = PrettyTable()
        pretty_table.field_names = ["Config", "Value"]
        pretty_table._max_width = {"Config": 50, "Value": 60}
        for attr, value in self.__dict__.items():
            if attr == "config":
                pretty_table.add_row([str(attr), str(value.pretty_table())])
            else:
                pretty_table.add_row([str(attr), str(value)])
        return str(pretty_table.get_string())

    def get_d(self):
        """
        Return a dict of class - exclude the _sa_instance_state
        :return: dict containing all attribs from class
        """
        return_dict = {}
        for key, value in self.__dict__.items():
            if '_sa_instance_state' not in key:
                return_dict[str(key)] = str(value)
        return return_dict

    def eject(self):
        """Eject disc if it hasn't previously been ejected
        """
        if self.ejected:
            logging.debug("The drive associated with this job has already been ejected.")
            return
        if self.drive is None:
            logging.warning("No drive was backpopulated with this job!")
            return
        if not cfg.arm_config['AUTO_EJECT']:
            logging.info("Skipping auto eject")
            self.drive.release_current_job()  # release job without ejecting
            return
        self.drive.eject()
        self.ejected = True

    @hybrid_property
    def finished(self):
        return JobState(self.status) in JOB_STATUS_FINISHED

    @finished.expression
    def finished(cls):
        return cls.status.in_([js.value for js in JOB_STATUS_FINISHED])

    @property
    def idle(self):
        return JobState(self.status) == JobState.IDLE

    @property
    def ripping(self):
        return JobState(self.status) in JOB_STATUS_RIPPING

    @property
    def run_time(self):
        return abs(dt.now() - self.start_time).total_seconds()

    @property
    def ripping_finished(self):
        """Indicates that the ripping process has finished.

        Note: This usually means that we are transcoding and the drive is not
              currently used.
        """
        if self.finished:
            logging.info("Job is finished.")
            return True
        if not self.ripping:
            logging.info("Job is not ripping.")
            return True
        if self.drive is None:
            logging.info("No drive was backpopulated with this job!")
            return True
        if self.ejected:
            logging.info(f"Drive {self.devpath} was ejected. No ripping process active.")
            return True
        logging.info(f"Job is ripping {self.devpath}.")
        return False

    @property
    def makemkv_source(self) -> str:
        """Return the MakeMKV source string for this job."""
        if self.source_type == SourceType.folder.value:
            return f"file:{self.source_path}"
        if self.source_type == SourceType.iso.value:
            return f"iso:{self.source_path}"
        return f"dev:{self.devpath}"

    @property
    def is_folder_import(self) -> bool:
        """Return True if this job was created from a folder import."""
        return self.source_type == SourceType.folder.value

    @property
    def is_iso_import(self) -> bool:
        """Return True if this job was created from an ISO file import."""
        return self.source_type == SourceType.iso.value

    @property
    def type_subfolder(self):
        """Map video_type to filesystem subfolder.

        Reads MOVIES_SUBDIR / TV_SUBDIR / AUDIO_SUBDIR / UNIDENTIFIED_SUBDIR
        from arm.yaml so ARM honors the same library-tree organization the
        transcoder uses. Falls back to legacy hardcoded defaults if
        arm_config is unavailable (test-isolation safety net).

        When video_type isn't a confirmed enum value (most commonly
        ``"unknown"`` for DVDs/Blu-rays/UHDs that didn't get an OMDB
        match before the rip started), fall back to MOVIES_SUBDIR for
        video discs. Most unidentified video discs are movies; routing
        them to ``unidentified/`` makes the operator triage every test
        rip. ``unidentified/`` stays for genuinely unclassifiable
        content (audio CDs without metadata, data discs).
        """
        import arm.config.config as cfg
        config_dict = getattr(cfg, 'arm_config', {}) or {}
        if self.video_type == "movie":
            return config_dict.get("MOVIES_SUBDIR", "movies")
        elif self.video_type == "series":
            return config_dict.get("TV_SUBDIR", "tv")
        elif self.video_type == "music":
            return config_dict.get("AUDIO_SUBDIR", "music")
        # Video disc without a confirmed type - default to MOVIES_SUBDIR.
        # Audio CDs go through "music" via ripping/abcde, so they reach
        # this branch only via the AUDIO_SUBDIR clause above.
        if self.disctype in ("dvd", "bluray", "uhd"):
            return config_dict.get("MOVIES_SUBDIR", "movies")
        return config_dict.get("UNIDENTIFIED_SUBDIR", "unidentified")

    def _pattern_fields_available(self):
        """Check if the structured fields needed for pattern rendering are populated.
        Movies: always available (just need title).
        Music: need artist or album.
        Series: need season or episode.
        """
        if self.video_type == 'music':
            return bool(
                getattr(self, 'artist', None) or getattr(self, 'artist_manual', None)
                or getattr(self, 'album', None) or getattr(self, 'album_manual', None)
            )
        elif self.video_type == 'series':
            return bool(
                getattr(self, 'season', None) or getattr(self, 'season_manual', None)
                or getattr(self, 'episode', None) or getattr(self, 'episode_manual', None)
            )
        return True

    @property
    def formatted_title(self):
        """Title formatted for filesystem paths, using pattern engine if available.
        Falls back to 'Title (Year)' or 'Title'."""
        if self._pattern_fields_available():
            try:
                from arm.ripper.naming import render_title
                result = render_title(self, cfg.arm_config)
                if result:
                    return result
            except Exception:
                pass
        title = self.title_manual if self.title_manual else self.title
        if self.year and self.year != "0000" and self.year != "":
            return f"{title} ({self.year})"
        return f"{title}"

    def build_raw_path(self):
        """Compute the raw rip directory path. Uses GUID for uniqueness -
        no dependency on title fields, no collision handling needed."""
        return os.path.join(str(self.config.RAW_PATH), str(self.guid))

    def build_transcode_path(self):
        """Compute the transcode output directory path, using folder pattern."""
        if self._pattern_fields_available():
            try:
                from arm.ripper.naming import render_folder
                folder = render_folder(self, cfg.arm_config)
                if folder:
                    return os.path.join(self.config.TRANSCODE_PATH, self.type_subfolder, folder)
            except Exception:
                pass
        return os.path.join(self.config.TRANSCODE_PATH, self.type_subfolder, self.formatted_title)

    def build_final_path(self):
        """Compute the final completed media directory path, using folder pattern.

        For TV series with USE_DISC_LABEL_FOR_TV enabled, uses disc label-based
        folder naming (e.g. "Breaking_Bad_S1D1").  When GROUP_TV_DISCS_UNDER_SERIES
        is also enabled, adds a parent series folder level.
        """
        from arm.ripper.utils import get_tv_folder_name, get_tv_series_parent_folder

        # TV series disc label naming overrides the normal pipeline
        if self.video_type == "series" and getattr(self.config, 'USE_DISC_LABEL_FOR_TV', False):
            folder = get_tv_folder_name(self)
            if not folder:
                folder = self.formatted_title
            if getattr(self.config, 'GROUP_TV_DISCS_UNDER_SERIES', False):
                parent = get_tv_series_parent_folder(self)
                return os.path.join(self.config.COMPLETED_PATH, self.type_subfolder, parent, folder)
            return os.path.join(self.config.COMPLETED_PATH, self.type_subfolder, folder)

        if self._pattern_fields_available():
            try:
                from arm.ripper.naming import render_folder
                folder = render_folder(self, cfg.arm_config)
                if folder:
                    return os.path.join(self.config.COMPLETED_PATH, self.type_subfolder, folder)
            except Exception:
                pass
        return os.path.join(self.config.COMPLETED_PATH, self.type_subfolder, self.formatted_title)
