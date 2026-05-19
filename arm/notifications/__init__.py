"""Notifications module — public surface only.

The rest of arm-neu must not import from this module's internals.
Only ``publish_event`` (the producer entry point) and ``router`` (the
FastAPI router) are part of the public API.
"""
# Public names are wired up in later tasks (events.py for publish_event,
# api.py for router). Keep this file minimal so other modules can't
# reach in through it.
