from arm.database import db


class AppState(db.Model):
    """Singleton table (one row, id=1) for global application state.

    Follows the same pattern as UISettings — a single-row table for
    app-wide toggles that need to survive restarts and be queryable
    from both the ripper and the UI.
    """
    __tablename__ = 'app_state'

    id = db.Column(db.Integer, primary_key=True)
    ripping_paused = db.Column(db.Boolean, default=False, nullable=False)

    @classmethod
    def get(cls):
        """Return the singleton row, creating it if it doesn't exist.

        Expires the cached instance first so we always read the latest
        value from the database — the web UI may have toggled the flag
        in a separate process/session.
        """
        state = cls.query.get(1)
        if state is None:
            state = cls(id=1, ripping_paused=False)
            db.session.add(state)
            db.session.commit()
        else:
            db.session.expire(state)
            db.session.refresh(state)
        return state

    def __repr__(self):
        return f'<AppState ripping_paused={self.ripping_paused}>'
