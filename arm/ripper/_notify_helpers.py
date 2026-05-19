"""Shared helpers for the notifications producer sites in the ripper.

These were originally private to ``arm_ripper`` (added in N17) but the
manual-wait and duplicate-disc paths (N18) need the same Disctype
mapping from ``makemkv.py`` and ``utils.py``. Extracting once here
avoids three near-identical copies.

This module is intentionally tiny — anything more interesting belongs
in ``arm.notifications`` rather than the ripper package.
"""
from arm_contracts.enums import Disctype


def job_disc_type(job) -> Disctype:
    """Map the ripper's string ``job.disctype`` column onto the contracts enum.

    A missing / empty / unrecognised value collapses to
    ``Disctype.unknown`` so the publish never blows up on an
    event-level required field; the upstream guard in
    ``notify_entry`` already rejects unknown discs before they reach
    the happy path.
    """
    if not job.disctype:
        return Disctype.unknown
    try:
        return Disctype(job.disctype)
    except ValueError:
        return Disctype.unknown
