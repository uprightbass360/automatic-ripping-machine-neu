"""Tests for ripper-internal enums (arm/enums.py)."""


def test_ripmethod_members():
    from arm.enums import RipMethod
    assert {m.value for m in RipMethod} == {"mkv", "backup", "backup_dvd"}


def test_ripmethod_str_serialization():
    from arm.enums import RipMethod
    assert str(RipMethod.backup_dvd) == "backup_dvd"
    assert f"{RipMethod.mkv}" == "mkv"


def test_audio_title_source_members():
    from arm.enums import AudioTitleSource
    assert {m.value for m in AudioTitleSource} == {
        "none", "musicbrainz", "freecddb",
    }
