"""Tests for database layer extraction (Phase 1)."""
from flask import Flask


class TestDatabaseLayer:
    def test_import_from_arm_database(self):
        """arm.database.db should be importable."""
        from arm.database import db
        assert db is not None

    def test_db_same_instance(self):
        """arm.ui.db and arm.database.db should be the same object."""
        from arm.database import db as db1
        from arm.ui import db as db2
        assert db1 is db2

    def test_init_db_binds_to_app(self, app_context):
        """init_db() should have bound db to the Flask app."""
        from arm.database import db

        app, _ = app_context
        # Verify we can query within the app context
        from arm.models.job import Job
        assert Job.query.all() == []

    def test_models_use_shared_db(self, app_context):
        """All models should use the shared db instance."""
        from arm.database import db
        from arm.models.job import Job
        from arm.models.notifications import Notifications
        from arm.models.track import Track
        from arm.models.user import User

        # All model classes should reference the same db metadata
        assert Job.metadata is db.metadata
        assert Notifications.metadata is db.metadata
        assert Track.metadata is db.metadata
        assert User.metadata is db.metadata
