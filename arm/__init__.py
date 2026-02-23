import arm.config  # noqa: F401
import arm.ripper  # noqa: F401
# arm.ui deliberately NOT imported here — it starts the Flask app + DB
# queries which fail in test environments without a migrated database.
