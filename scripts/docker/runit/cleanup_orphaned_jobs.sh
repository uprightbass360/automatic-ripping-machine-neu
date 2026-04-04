#!/bin/bash
# One-shot cleanup of orphaned jobs on container startup.
# Runs after arm_user_files_setup.sh, before start_udev.sh (alphabetical order).
# Must NOT block container startup — a failed cleanup is logged and skipped.

echo "[ARM] Cleaning up orphaned jobs from previous run..."

cd /opt/arm

# Run cleanup as the arm user with the same Python environment.
# Errors are caught so the container always boots even if the DB is missing.
if /sbin/setuser arm /bin/python3 -c "
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

import arm.config.config as cfg
from arm.database import db
db.init_engine('sqlite:///' + cfg.arm_config['DBFILE'])

from arm.services.job_cleanup import cleanup_orphaned_jobs
count = cleanup_orphaned_jobs()
if count:
    print(f'[ARM] Cleaned up {count} orphaned job(s)')
else:
    print('[ARM] No orphaned jobs found')
"; then
    echo "[ARM] Orphaned job cleanup complete"
else
    echo "[ARM] WARNING: Orphaned job cleanup failed — continuing startup"
fi
