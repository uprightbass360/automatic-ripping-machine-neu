""" Main file for running DVDs/Blu-rays/CDs/data ?
It would help clear up main and make things easier to find
"""
import logging
from importlib.util import find_spec
from pathlib import Path
import sys

# If the arm module can't be found, add the folder this file is in to PYTHONPATH
# This is a bad workaround for non-existent packaging
if find_spec("arm") is None:
    sys.path.append(str(Path(__file__).parents[2]))

from arm.ripper import utils, makemkv  # noqa E402
from arm.database import db  # noqa E402
import arm.constants as constants  # noqa E402
from arm.models.job import JobState  # noqa E402


def _post_rip_handoff(job):
    """Decide whether to hand off to the transcoder or finalize locally.

    Decision logic:
      1. If TRANSCODER_URL is empty → finalize locally (no transcoder at all).
      2. If the per-job config has SKIP_TRANSCODE set (not None) → use it.
      3. Otherwise fall back to the global SKIP_TRANSCODE (default False).

    When skipping: finalize output, set SUCCESS, commit.
    When not skipping: fire the transcoder webhook.
    Always handles NOTIFY_RIP notification.
    """
    import arm.config.config as cfg
    from arm.ripper.naming import finalize_output

    transcoder_url = cfg.arm_config.get('TRANSCODER_URL', '')

    # Determine skip_transcode value: per-job override > global config
    if job.config.SKIP_TRANSCODE is not None:
        skip = job.config.SKIP_TRANSCODE
    else:
        skip = cfg.arm_config.get('SKIP_TRANSCODE', False)

    if not transcoder_url or skip:
        reason = "SKIP_TRANSCODE is enabled" if skip else "No transcoder configured"
        logging.info("%s - finalizing output locally", reason)
        finalize_output(job)
        job.status = JobState.SUCCESS.value
        db.session.commit()
    else:
        utils.transcoder_notify(
            cfg.arm_config, constants.NOTIFY_TITLE,
            f"{job.title} rip complete.", job,
        )

    if job.config.NOTIFY_RIP:
        utils.notify(job, constants.NOTIFY_TITLE, f"{job.title} rip complete.")


def rip_visual_media(have_dupes, job, logfile, protection):
    """
    Main ripping function for dvd and Blu-rays, movies or series.

    Pipeline: rip with MakeMKV -> persist paths to DB -> notify -> done.
    Transcoding is handled by the external transcoder service.

    :param have_dupes: Does this disc already exist in the database
    :param job: Current job
    :param logfile: Current logfile
    :param protection: Does the disc have 99 track protection
    :return: None
    """
    # Compute final path for DB/webhook metadata
    final_directory = job.build_final_path()

    # Check folders for already ripped jobs -> creates folder (handles collisions)
    final_directory = utils.check_for_dupe_folder(have_dupes, final_directory, job)

    # Persist path to DB
    utils.database_updater({'path': final_directory}, job)
    # Save poster image from disc if enabled
    utils.save_disc_poster(final_directory, job)

    logging.info("************* Ripping disc with MakeMKV *************")
    job.status = JobState.VIDEO_RIPPING.value
    db.session.commit()
    try:
        makemkv_out_path = makemkv.makemkv(job)
    except makemkv.UpdateKeyRunTimeError as key_error:
        raise utils.RipperException(
            "MakeMKV key update failed — cannot decrypt discs. "
            "Check network access to forum.makemkv.com or set "
            "MAKEMKV_PERMA_KEY in arm.yaml."
        ) from key_error
    except Exception as mkv_error:
        raise utils.RipperException(f"Error while running MakeMKV: {mkv_error}") from mkv_error

    # Persist raw_path to DB — this is the actual directory on disk
    utils.database_updater({'raw_path': makemkv_out_path}, job)

    _post_rip_handoff(job)
    logging.info("************* Ripping with MakeMKV completed *************")

    # Report errors if any
    notify_exit(job)
    logging.info("************* ARM processing complete *************")


def notify_exit(job):
    """
    Notify post ripping - ARM finished\n
    Includes any errors
    :param job: current job
    :return: None
    """
    if job.config.NOTIFY_TRANSCODE:
        if job.errors:
            errlist = ', '.join(job.errors)
            utils.notify(job, constants.NOTIFY_TITLE,
                         f" {job.title} processing completed with errors. "
                         f"Title(s) {errlist} failed to complete. ")
            logging.info(f"Processing completed with errors.  Title(s) {errlist} failed to complete. ")
        else:
            utils.notify(job, constants.NOTIFY_TITLE, f"{job.title} {constants.PROCESS_COMPLETE}")
