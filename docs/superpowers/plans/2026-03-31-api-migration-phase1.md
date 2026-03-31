# ARM API Migration Phase 1 - New Endpoints

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add missing ARM API endpoints so the UI can stop reading/writing the ARM database directly. This phase covers the ARM backend only - new endpoints + tests. Phase 2 (separate plan, UI repo) will wire the UI to use these endpoints.

**Architecture:** Add 4 new endpoint groups to existing ARM API routers: notifications CRUD, drives listing, job detail enrichment, and notification bulk operations. All endpoints follow existing patterns (sync def, JSONResponse for errors, SQLAlchemy queries).

**Tech Stack:** FastAPI, SQLAlchemy, pytest, existing ARM models (Notifications, SystemDrives, Job, Track, AppState)

**Branch:** `feat/api-migration-phase1` on `automatic-ripping-machine-neu`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `arm/api/v1/notifications.py` | Modify | Add list, count, dismiss-all, purge endpoints |
| `arm/api/v1/drives.py` | Modify | Add GET /drives listing endpoint |
| `arm/api/v1/jobs.py` | Modify | Add single-job detail with config + track counts |
| `test/test_api.py` | Modify | Add tests for all new endpoints |
| `test/conftest.py` | Modify | Add notification + drive fixtures |

---

### Task 1: Notification Fixtures

**Files:**
- Modify: `test/conftest.py`

- [ ] **Step 1: Add notification fixture**

```python
@pytest.fixture
def sample_notifications(app_context):
    """Create test notifications: 2 unseen, 1 seen, 1 cleared."""
    import datetime
    from arm.models.notifications import Notifications
    from arm.database import db

    now = datetime.datetime.now()

    n1 = Notifications("Job Complete", "Movie ripped successfully")
    n1.trigger_time = now - datetime.timedelta(hours=2)

    n2 = Notifications("Job Started", "Ripping disc")
    n2.trigger_time = now - datetime.timedelta(hours=1)

    n3 = Notifications("Old Job", "Already read")
    n3.seen = True
    n3.dismiss_time = now - datetime.timedelta(minutes=30)
    n3.trigger_time = now - datetime.timedelta(hours=3)

    n4 = Notifications("Cleared Job", "Gone")
    n4.seen = True
    n4.cleared = True
    n4.cleared_time = now - datetime.timedelta(minutes=10)
    n4.trigger_time = now - datetime.timedelta(hours=4)

    db.session.add_all([n1, n2, n3, n4])
    db.session.commit()
    return [n1, n2, n3, n4]
```

- [ ] **Step 2: Add drive fixture**

```python
@pytest.fixture
def sample_drives(app_context):
    """Create test drives: 1 active with job, 1 idle, 1 stale."""
    from arm.models.system_drives import SystemDrives
    from arm.database import db

    d1 = SystemDrives()
    d1.name = "Living Room"
    d1.mount = "/dev/sr0"
    d1.maker = "PIONEER"
    d1.model = "BD-RW BDR-S12JX"
    d1.firmware = "1.01"
    d1.read_cd = True
    d1.read_dvd = True
    d1.read_bd = True
    d1.stale = False

    d2 = SystemDrives()
    d2.name = "Office"
    d2.mount = "/dev/sr1"
    d2.maker = "LG"
    d2.model = "WH16NS60"
    d2.firmware = "1.02"
    d2.read_cd = True
    d2.read_dvd = True
    d2.read_bd = True
    d2.stale = False

    d3 = SystemDrives()
    d3.name = "Stale Drive"
    d3.mount = "/dev/sr2"
    d3.stale = True

    db.session.add_all([d1, d2, d3])
    db.session.commit()
    return [d1, d2, d3]
```

- [ ] **Step 3: Verify fixtures load**

Run: `python3 -m pytest test/conftest.py --co -q`
Expected: No import errors

- [ ] **Step 4: Commit**

```bash
git add test/conftest.py
git commit -m "test: add notification and drive fixtures for API migration"
```

---

### Task 2: Notification List Endpoint

**Files:**
- Modify: `arm/api/v1/notifications.py`
- Modify: `test/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
class TestApiNotificationsList:
    """Test GET /api/v1/notifications endpoint."""

    def test_list_unseen_only(self, client, sample_notifications):
        response = client.get('/api/v1/notifications')
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 2
        # Unseen only by default
        for n in data["notifications"]:
            assert n["seen"] is False

    def test_list_include_cleared(self, client, sample_notifications):
        response = client.get('/api/v1/notifications?include_cleared=true')
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 4

    def test_list_empty(self, client, app_context):
        response = client.get('/api/v1/notifications')
        assert response.status_code == 200
        assert response.json()["notifications"] == []

    def test_list_ordered_newest_first(self, client, sample_notifications):
        response = client.get('/api/v1/notifications')
        data = response.json()
        times = [n["trigger_time"] for n in data["notifications"]]
        assert times == sorted(times, reverse=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test/test_api.py::TestApiNotificationsList -v`
Expected: FAIL - endpoint returns wrong format

- [ ] **Step 3: Implement the endpoint**

In `arm/api/v1/notifications.py`, add:

```python
import datetime
from arm.database import db
from arm.models.notifications import Notifications


@router.get('/notifications')
def list_notifications(include_cleared: bool = False):
    """List notifications, newest first. Excludes cleared by default."""
    query = Notifications.query
    if not include_cleared:
        query = query.filter(Notifications.cleared == False)  # noqa: E712
    notifications = query.order_by(Notifications.trigger_time.desc()).all()
    return {
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "seen": n.seen,
                "cleared": n.cleared,
                "trigger_time": n.trigger_time.isoformat() if n.trigger_time else None,
                "dismiss_time": n.dismiss_time.isoformat() if n.dismiss_time else None,
            }
            for n in notifications
        ],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test/test_api.py::TestApiNotificationsList -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add arm/api/v1/notifications.py test/test_api.py
git commit -m "feat: add GET /notifications endpoint for listing notifications"
```

---

### Task 3: Notification Count Endpoint

**Files:**
- Modify: `arm/api/v1/notifications.py`
- Modify: `test/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
class TestApiNotificationCount:
    """Test GET /api/v1/notifications/count endpoint."""

    def test_count_with_notifications(self, client, sample_notifications):
        response = client.get('/api/v1/notifications/count')
        assert response.status_code == 200
        data = response.json()
        assert data["unseen"] == 2
        assert data["seen"] == 1
        assert data["cleared"] == 1
        assert data["total"] == 4

    def test_count_empty(self, client, app_context):
        response = client.get('/api/v1/notifications/count')
        assert response.status_code == 200
        data = response.json()
        assert data["unseen"] == 0
        assert data["total"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test/test_api.py::TestApiNotificationCount -v`
Expected: FAIL - 404

- [ ] **Step 3: Implement the endpoint**

```python
from sqlalchemy import func


@router.get('/notifications/count')
def notification_count():
    """Return notification counts by status."""
    total = Notifications.query.count()
    unseen = Notifications.query.filter(
        Notifications.seen == False  # noqa: E712
    ).count()
    cleared = Notifications.query.filter(
        Notifications.cleared == True  # noqa: E712
    ).count()
    seen = total - unseen - cleared
    return {
        "unseen": unseen,
        "seen": seen,
        "cleared": cleared,
        "total": total,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test/test_api.py::TestApiNotificationCount -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add arm/api/v1/notifications.py test/test_api.py
git commit -m "feat: add GET /notifications/count endpoint"
```

---

### Task 4: Notification Dismiss-All Endpoint

**Files:**
- Modify: `arm/api/v1/notifications.py`
- Modify: `test/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
class TestApiNotificationDismissAll:
    """Test POST /api/v1/notifications/dismiss-all endpoint."""

    def test_dismiss_all(self, client, sample_notifications):
        response = client.post('/api/v1/notifications/dismiss-all')
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 2  # only unseen get dismissed

        # Verify all are now seen
        check = client.get('/api/v1/notifications/count')
        assert check.json()["unseen"] == 0

    def test_dismiss_all_none_unseen(self, client, app_context):
        response = client.post('/api/v1/notifications/dismiss-all')
        assert response.status_code == 200
        assert response.json()["count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test/test_api.py::TestApiNotificationDismissAll -v`
Expected: FAIL - 404 or 405

- [ ] **Step 3: Implement the endpoint**

```python
@router.post('/notifications/dismiss-all')
def dismiss_all_notifications():
    """Mark all unseen notifications as seen."""
    import datetime
    now = datetime.datetime.now()
    count = (
        Notifications.query
        .filter(Notifications.seen == False)  # noqa: E712
        .update({"seen": True, "dismiss_time": now})
    )
    db.session.commit()
    return {"success": True, "count": count}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test/test_api.py::TestApiNotificationDismissAll -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add arm/api/v1/notifications.py test/test_api.py
git commit -m "feat: add POST /notifications/dismiss-all endpoint"
```

---

### Task 5: Notification Purge Endpoint

**Files:**
- Modify: `arm/api/v1/notifications.py`
- Modify: `test/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
class TestApiNotificationPurge:
    """Test POST /api/v1/notifications/purge endpoint."""

    def test_purge_cleared(self, client, sample_notifications):
        response = client.post('/api/v1/notifications/purge')
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1  # only cleared get purged

        # Verify total decreased
        check = client.get('/api/v1/notifications/count')
        assert check.json()["total"] == 3
        assert check.json()["cleared"] == 0

    def test_purge_none_cleared(self, client, app_context):
        response = client.post('/api/v1/notifications/purge')
        assert response.status_code == 200
        assert response.json()["count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test/test_api.py::TestApiNotificationPurge -v`
Expected: FAIL - 404 or 405

- [ ] **Step 3: Implement the endpoint**

```python
@router.post('/notifications/purge')
def purge_cleared_notifications():
    """Hard-delete all cleared notifications."""
    count = (
        Notifications.query
        .filter(Notifications.cleared == True)  # noqa: E712
        .delete()
    )
    db.session.commit()
    return {"success": True, "count": count}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test/test_api.py::TestApiNotificationPurge -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add arm/api/v1/notifications.py test/test_api.py
git commit -m "feat: add POST /notifications/purge endpoint"
```

---

### Task 6: Drives Listing Endpoint

**Files:**
- Modify: `arm/api/v1/drives.py`
- Modify: `test/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
class TestApiDrivesList:
    """Test GET /api/v1/drives endpoint."""

    def test_list_drives(self, client, sample_drives):
        response = client.get('/api/v1/drives')
        assert response.status_code == 200
        data = response.json()
        # Should exclude stale drives by default
        assert len(data["drives"]) == 2
        names = [d["name"] for d in data["drives"]]
        assert "Living Room" in names
        assert "Office" in names
        assert "Stale Drive" not in names

    def test_list_drives_include_stale(self, client, sample_drives):
        response = client.get('/api/v1/drives?include_stale=true')
        assert response.status_code == 200
        assert len(response.json()["drives"]) == 3

    def test_list_drives_empty(self, client, app_context):
        response = client.get('/api/v1/drives')
        assert response.status_code == 200
        assert response.json()["drives"] == []

    def test_drive_includes_capabilities(self, client, sample_drives):
        response = client.get('/api/v1/drives')
        data = response.json()
        drive = next(d for d in data["drives"] if d["name"] == "Living Room")
        assert "capabilities" in drive
        assert "BD" in drive["capabilities"]

    def test_drive_includes_job_ids(self, client, sample_drives):
        response = client.get('/api/v1/drives')
        data = response.json()
        drive = data["drives"][0]
        assert "job_id_current" in drive
        assert "job_id_previous" in drive
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test/test_api.py::TestApiDrivesList -v`
Expected: FAIL - 404 or wrong format

- [ ] **Step 3: Implement the endpoint**

In `arm/api/v1/drives.py`, add before the diagnostic endpoint:

```python
@router.get('/drives')
def list_drives(include_stale: bool = False):
    """List optical drives with capabilities and current/previous job IDs."""
    query = SystemDrives.query
    if not include_stale:
        query = query.filter(SystemDrives.stale == False)  # noqa: E712
    drives = query.all()

    def _capabilities(d):
        caps = []
        if d.read_cd:
            caps.append("CD")
        if d.read_dvd:
            caps.append("DVD")
        if d.read_bd:
            caps.append("BD")
        if getattr(d, 'uhd_capable', False):
            caps.append("UHD")
        return caps

    return {
        "drives": [
            {
                "drive_id": d.drive_id,
                "name": d.name,
                "description": getattr(d, 'description', ''),
                "mount": d.mount,
                "maker": d.maker,
                "model": d.model,
                "serial": d.serial,
                "firmware": d.firmware,
                "connection": d.connection,
                "capabilities": _capabilities(d),
                "uhd_capable": getattr(d, 'uhd_capable', False),
                "drive_mode": getattr(d, 'drive_mode', 'auto'),
                "stale": d.stale,
                "job_id_current": d.job_id_current,
                "job_id_previous": d.job_id_previous,
            }
            for d in drives
        ],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test/test_api.py::TestApiDrivesList -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add arm/api/v1/drives.py test/test_api.py
git commit -m "feat: add GET /drives listing endpoint with capabilities"
```

---

### Task 7: Drives-With-Jobs Endpoint

**Files:**
- Modify: `arm/api/v1/drives.py`
- Modify: `test/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
class TestApiDrivesWithJobs:
    """Test GET /api/v1/drives/with-jobs endpoint."""

    def test_drives_with_current_job(self, client, sample_drives, sample_job, app_context):
        from arm.database import db
        # Assign sample_job to first drive
        sample_drives[0].job_id_current = sample_job.job_id
        db.session.commit()

        response = client.get('/api/v1/drives/with-jobs')
        assert response.status_code == 200
        data = response.json()
        drive = next(d for d in data["drives"] if d["name"] == "Living Room")
        assert drive["current_job"] is not None
        assert drive["current_job"]["title"] == "SERIAL_MOM"
        assert drive["current_job"]["status"] == "active"

    def test_drives_without_jobs(self, client, sample_drives):
        response = client.get('/api/v1/drives/with-jobs')
        data = response.json()
        for drive in data["drives"]:
            assert drive["current_job"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test/test_api.py::TestApiDrivesWithJobs -v`
Expected: FAIL - 404

- [ ] **Step 3: Implement the endpoint**

```python
from arm.models.job import Job


@router.get('/drives/with-jobs')
def list_drives_with_jobs():
    """List non-stale drives with current job details attached."""
    drives = (
        SystemDrives.query
        .filter(SystemDrives.stale == False)  # noqa: E712
        .all()
    )

    def _capabilities(d):
        caps = []
        if d.read_cd:
            caps.append("CD")
        if d.read_dvd:
            caps.append("DVD")
        if d.read_bd:
            caps.append("BD")
        if getattr(d, 'uhd_capable', False):
            caps.append("UHD")
        return caps

    def _job_summary(job_id):
        if not job_id:
            return None
        job = Job.query.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "title": job.title,
            "year": job.year,
            "video_type": job.video_type,
            "status": job.status,
            "stage": job.stage,
            "disctype": job.disctype,
            "label": job.label,
            "poster_url": job.poster_url,
            "no_of_titles": job.no_of_titles,
        }

    return {
        "drives": [
            {
                "drive_id": d.drive_id,
                "name": d.name,
                "description": getattr(d, 'description', ''),
                "mount": d.mount,
                "maker": d.maker,
                "model": d.model,
                "firmware": d.firmware,
                "connection": d.connection,
                "capabilities": _capabilities(d),
                "uhd_capable": getattr(d, 'uhd_capable', False),
                "drive_mode": getattr(d, 'drive_mode', 'auto'),
                "job_id_current": d.job_id_current,
                "job_id_previous": d.job_id_previous,
                "current_job": _job_summary(d.job_id_current),
            }
            for d in drives
        ],
    }
```

**Note:** Place `list_drives_with_jobs` BEFORE `drive_diagnostic` in the file so the route `/drives/with-jobs` is registered before `/drives/diagnostic`. Both are GET so order matters.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test/test_api.py::TestApiDrivesWithJobs -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add arm/api/v1/drives.py test/test_api.py
git commit -m "feat: add GET /drives/with-jobs endpoint with current job details"
```

---

### Task 8: Job Detail Endpoint (Single Job + Config + Track Counts)

**Files:**
- Modify: `arm/api/v1/jobs.py`
- Modify: `test/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
class TestApiJobDetail:
    """Test GET /api/v1/jobs/<id>/detail endpoint."""

    def test_job_detail_basic(self, client, sample_job, app_context):
        response = client.get(f'/api/v1/jobs/{sample_job.job_id}/detail')
        assert response.status_code == 200
        data = response.json()
        assert data["job"]["title"] == "SERIAL_MOM"
        assert data["job"]["year"] == "1994"
        assert "config" in data
        assert "track_counts" in data

    def test_job_detail_track_counts(self, client, sample_job, app_context):
        from arm.models.track import Track
        from arm.database import db

        # Add tracks: 2 ripped, 1 not
        for i in range(3):
            t = Track(
                job_id=sample_job.job_id,
                track_number=str(i),
                length=3600,
                main_feature=i == 0,
                basename=f"title_{i}.mkv",
            )
            t.ripped = i < 2
            db.session.add(t)
        db.session.commit()

        response = client.get(f'/api/v1/jobs/{sample_job.job_id}/detail')
        data = response.json()
        assert data["track_counts"]["total"] == 3
        assert data["track_counts"]["ripped"] == 2

    def test_job_detail_not_found(self, client, app_context):
        response = client.get('/api/v1/jobs/99999/detail')
        assert response.status_code == 404

    def test_job_detail_config_masks_sensitive(self, client, sample_job, app_context):
        response = client.get(f'/api/v1/jobs/{sample_job.job_id}/detail')
        data = response.json()
        config = data["config"]
        # Sensitive fields should not appear or should be masked
        for key in ("PB_KEY", "IFTTT_KEY", "PO_USER_KEY", "PO_APP_KEY",
                     "EMBY_PASSWORD", "EMBY_API_KEY"):
            if key in config:
                assert config[key] in (None, "", "***")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test/test_api.py::TestApiJobDetail -v`
Expected: FAIL - 404

- [ ] **Step 3: Implement the endpoint**

In `arm/api/v1/jobs.py`, add:

```python
HIDDEN_CONFIG_FIELDS = {
    "PB_KEY", "IFTTT_KEY", "PO_USER_KEY", "PO_APP_KEY",
    "EMBY_PASSWORD", "EMBY_API_KEY", "OMDB_API_KEY",
    "TMDB_API_KEY", "TVDB_API_KEY", "MAKEMKV_PERMA_KEY",
    "ARM_API_KEY", "JSON_URL", "EMBY_USERID", "EMBY_USERNAME",
}


@router.get('/jobs/{job_id}/detail')
def get_job_detail(job_id: int):
    """Return job with config (masked) and track counts."""
    job = Job.query.get(job_id)
    if not job:
        return JSONResponse({"success": False, "error": _JOB_NOT_FOUND}, status_code=404)

    # Job fields
    job_data = {
        col.name: getattr(job, col.name)
        for col in Job.__table__.columns
    }
    # Serialize datetimes
    for key, val in job_data.items():
        if hasattr(val, 'isoformat'):
            job_data[key] = val.isoformat()

    # Config (masked)
    config_data = None
    if job.config:
        config_data = {}
        from arm.models.config import Config
        for col in Config.__table__.columns:
            name = col.name
            if name in ("CONFIG_ID", "job_id"):
                continue
            value = getattr(job.config, name, None)
            if name in HIDDEN_CONFIG_FIELDS:
                config_data[name] = "***" if value else None
            else:
                config_data[name] = value

    # Track counts
    tracks = Track.query.filter_by(job_id=job_id).all()
    ripped = sum(1 for t in tracks if t.ripped)

    return {
        "job": job_data,
        "config": config_data,
        "track_counts": {
            "total": len(tracks),
            "ripped": ripped,
        },
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test/test_api.py::TestApiJobDetail -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add arm/api/v1/jobs.py test/test_api.py
git commit -m "feat: add GET /jobs/{id}/detail with config and track counts"
```

---

### Task 9: Active Jobs Endpoint (Dashboard)

**Files:**
- Modify: `arm/api/v1/jobs.py`
- Modify: `test/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
class TestApiActiveJobs:
    """Test GET /api/v1/jobs/active endpoint."""

    def test_active_jobs_returns_active(self, client, sample_job, app_context):
        response = client.get('/api/v1/jobs/active')
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["title"] == "SERIAL_MOM"
        assert "track_counts" in data["jobs"][0]

    def test_active_jobs_excludes_completed(self, client, sample_job, app_context):
        from arm.database import db
        sample_job.status = "success"
        db.session.commit()

        response = client.get('/api/v1/jobs/active')
        assert response.json()["jobs"] == []

    def test_active_jobs_with_tracks(self, client, sample_job, app_context):
        from arm.models.track import Track
        from arm.database import db

        for i in range(2):
            t = Track(
                job_id=sample_job.job_id,
                track_number=str(i),
                length=3600,
                main_feature=i == 0,
                basename=f"title_{i}.mkv",
            )
            t.ripped = i == 0
            db.session.add(t)
        db.session.commit()

        response = client.get('/api/v1/jobs/active')
        job = response.json()["jobs"][0]
        assert job["track_counts"]["total"] == 2
        assert job["track_counts"]["ripped"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test/test_api.py::TestApiActiveJobs -v`
Expected: FAIL - 404

- [ ] **Step 3: Implement the endpoint**

```python
_ACTIVE_STATUSES = {"active", "ripping", "transcoding", "waiting"}


@router.get('/jobs/active')
def get_active_jobs():
    """Return jobs with active statuses, including track counts.

    Used by the dashboard to show currently running/waiting jobs.
    """
    jobs = Job.query.filter(Job.status.in_(_ACTIVE_STATUSES)).all()
    result = []
    for job in jobs:
        job_data = {
            col.name: getattr(job, col.name)
            for col in Job.__table__.columns
        }
        for key, val in job_data.items():
            if hasattr(val, 'isoformat'):
                job_data[key] = val.isoformat()

        tracks = Track.query.filter_by(job_id=job.job_id).all()
        ripped = sum(1 for t in tracks if t.ripped)
        job_data["track_counts"] = {"total": len(tracks), "ripped": ripped}
        result.append(job_data)

    return {"jobs": result}
```

**Important:** Place this BEFORE the `'/jobs/{job_id}'` routes in jobs.py so FastAPI doesn't try to parse "active" as a job_id.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test/test_api.py::TestApiActiveJobs -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add arm/api/v1/jobs.py test/test_api.py
git commit -m "feat: add GET /jobs/active endpoint with track counts for dashboard"
```

---

### Task 10: Full Test Suite Verification + Push

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest test/ -v --tb=short`
Expected: All tests pass (existing + new)

- [ ] **Step 2: Check for any import issues or circular dependencies**

Run: `python3 -c "from arm.api.v1 import notifications, drives, jobs, system; print('OK')"`
Expected: OK

- [ ] **Step 3: Push branch**

```bash
git push -u origin feat/api-migration-phase1
```

---

## Phase 2 Documentation (For Tomorrow)

Phase 2 will be a separate plan in the UI repo (`automatic-ripping-machine-ui`). It involves:

### UI Backend Changes (arm_client.py)

Add proxy functions for new ARM endpoints:
- `list_notifications(include_cleared)` -> `GET /api/v1/notifications`
- `get_notification_count()` -> `GET /api/v1/notifications/count`
- `dismiss_all_notifications()` -> `POST /api/v1/notifications/dismiss-all`
- `purge_cleared_notifications()` -> `POST /api/v1/notifications/purge`
- `list_drives(include_stale)` -> `GET /api/v1/drives`
- `list_drives_with_jobs()` -> `GET /api/v1/drives/with-jobs`
- `get_job_detail(job_id)` -> `GET /api/v1/jobs/{id}/detail`
- `get_active_jobs()` -> `GET /api/v1/jobs/active`

### UI Router Changes

Replace `arm_db` calls with `arm_client` calls in:
- `dashboard.py` - swap get_active_jobs, get_drives, get_notification_count, get_ripping_paused, is_available
- `notifications.py` - swap get_notifications
- `maintenance.py` - swap notification count/dismiss/purge
- `drives.py` - swap get_drives_with_jobs
- `jobs.py` - swap get_job, get_jobs_paginated, get_job_with_config, get_job_track_counts
- `settings.py` - swap get_all_config_safe, get_drives, is_available

### arm_db.py Cleanup

Remove migrated functions from arm_db.py. Goal: only `is_available()` remains as a fallback health check.

### Testing

Update all UI backend tests that mock arm_db to mock arm_client instead.
