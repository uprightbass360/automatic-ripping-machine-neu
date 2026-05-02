"""Ripper-internal enums.

Values that never cross a service boundary live here. Anything that
appears in a webhook payload, callback payload, or HTTP API response
that arm-ui consumes belongs in arm_contracts.enums instead.
"""
from enum import Enum


class _StrValueEnum(str, Enum):
    """Base for string-valued enums; mirrors arm_contracts._StrValueEnum
    so we don't drag the contracts package in for ripper-only types."""

    def __str__(self) -> str:
        return self.value

    def __format__(self, format_spec: str) -> str:
        return self.value.__format__(format_spec)


class RipMethod(_StrValueEnum):
    """MakeMKV rip strategy. Used for Job.config.RIPMETHOD.

    backup / backup_dvd are Blu-ray strategies (backup decrypts then
    copies; backup_dvd extracts via MakeMKV before post-processing).
    mkv is the default direct-to-MKV path used for DVDs and most
    Blu-rays.
    """
    mkv = "mkv"
    backup = "backup"
    backup_dvd = "backup_dvd"


class AudioTitleSource(_StrValueEnum):
    """Audio CD title lookup source. Used for Job.config.GET_AUDIO_TITLE."""
    none = "none"
    musicbrainz = "musicbrainz"
    freecddb = "freecddb"
