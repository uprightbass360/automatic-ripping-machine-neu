"""Shared database layer — imported by models, ripper, and UI."""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def init_db(app):
    """Bind db and migrate to Flask app. Called once at startup."""
    db.init_app(app)
    migrate.init_app(app, db)
