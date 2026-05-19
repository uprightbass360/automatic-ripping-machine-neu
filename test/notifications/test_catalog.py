"""Tests for the apprise-introspected service catalog."""
from unittest.mock import patch, MagicMock

import pytest


def _fake_plugin(*, service_name, service_url, protocols, secure_protocols,
                 template_tokens, template_args):
    """Build a mock that quacks like an apprise plugin class."""
    cls = MagicMock()
    cls.service_name = service_name
    cls.service_url = service_url
    cls.protocol = protocols
    cls.secure_protocol = secure_protocols
    cls.template_tokens = template_tokens
    cls.template_args = template_args
    cls.__name__ = f"Notify{service_name}"
    return cls


def _lazy(s):
    """LazyTranslation stand-in for tests — apprise wraps labels."""
    m = MagicMock()
    m.__str__ = lambda self: s
    return m


def test_catalog_returns_featured_and_all():
    from arm.notifications.catalog import build_catalog

    fake_plugin = _fake_plugin(
        service_name="Discord",
        service_url="https://github.com/caronc/apprise/wiki/Notify_discord",
        protocols=None,
        secure_protocols="discord",
        template_tokens={
            "webhook_id": {"name": _lazy("Webhook ID"),
                           "type": "string", "private": True, "required": True},
            "webhook_token": {"name": _lazy("Webhook Token"),
                              "type": "string", "private": True, "required": True},
        },
        template_args={
            "tts": {"name": _lazy("TTS"), "type": "bool", "default": False},
        },
    )
    fake_mgr = MagicMock()
    fake_mgr.plugins.return_value = [fake_plugin]
    with patch("arm.notifications.catalog._get_manager",
               return_value=fake_mgr):
        catalog = build_catalog()
    assert "featured" in catalog
    assert "services" in catalog
    assert any(s["id"] == "discord" for s in catalog["services"])


def test_catalog_filters_operational_args():
    """Operational args like verify, rto, cto, store, tz, overflow
    must be excluded from advanced_fields."""
    from arm.notifications.catalog import build_catalog

    fake_plugin = _fake_plugin(
        service_name="Discord",
        service_url="https://example",
        protocols=None,
        secure_protocols="discord",
        template_tokens={
            "webhook_id": {"name": _lazy("Webhook ID"),
                           "type": "string", "private": True, "required": True},
        },
        template_args={
            "tts": {"name": _lazy("TTS"), "type": "bool", "default": False},
            "verify": {"name": _lazy("Verify"), "type": "bool", "default": True},
            "rto": {"name": _lazy("RTO"), "type": "float", "default": 4.0},
            "cto": {"name": _lazy("CTO"), "type": "float", "default": 4.0},
            "store": {"name": _lazy("Store"), "type": "bool", "default": True},
            "tz": {"name": _lazy("TZ"), "type": "string", "default": None},
            "overflow": {"name": _lazy("Overflow"),
                         "type": "choice:string",
                         "values": frozenset({"split", "truncate", "upstream"}),
                         "default": "upstream"},
        },
    )
    fake_mgr = MagicMock()
    fake_mgr.plugins.return_value = [fake_plugin]
    with patch("arm.notifications.catalog._get_manager",
               return_value=fake_mgr):
        catalog = build_catalog()
    discord = next(s for s in catalog["services"] if s["id"] == "discord")
    advanced_keys = {f["key"] for f in discord["advanced_fields"]}
    assert "tts" in advanced_keys
    assert "verify" not in advanced_keys
    assert "rto" not in advanced_keys
    assert "cto" not in advanced_keys
    assert "store" not in advanced_keys
    assert "tz" not in advanced_keys
    assert "overflow" not in advanced_keys


def test_catalog_required_fields_have_private_flag():
    from arm.notifications.catalog import build_catalog

    fake_plugin = _fake_plugin(
        service_name="Discord",
        service_url="https://example",
        protocols=None,
        secure_protocols="discord",
        template_tokens={
            "webhook_id": {"name": _lazy("Webhook ID"),
                           "type": "string", "private": True, "required": True},
        },
        template_args={},
    )
    fake_mgr = MagicMock()
    fake_mgr.plugins.return_value = [fake_plugin]
    with patch("arm.notifications.catalog._get_manager",
               return_value=fake_mgr):
        catalog = build_catalog()
    discord = next(s for s in catalog["services"] if s["id"] == "discord")
    assert discord["required_fields"][0]["private"] is True


def test_catalog_choice_string_exposes_values():
    """Type 'choice:string' must expose the allowed values list."""
    from arm.notifications.catalog import build_catalog

    fake_plugin = _fake_plugin(
        service_name="Discord",
        service_url="https://example",
        protocols=None,
        secure_protocols="discord",
        template_tokens={
            "webhook_id": {"name": _lazy("Webhook ID"),
                           "type": "string", "required": True},
        },
        template_args={
            "format": {"name": _lazy("Format"),
                       "type": "choice:string",
                       "values": frozenset({"html", "text", "markdown"}),
                       "default": "text"},
        },
    )
    fake_mgr = MagicMock()
    fake_mgr.plugins.return_value = [fake_plugin]
    with patch("arm.notifications.catalog._get_manager",
               return_value=fake_mgr):
        catalog = build_catalog()
    discord = next(s for s in catalog["services"] if s["id"] == "discord")
    fmt = next(f for f in discord["advanced_fields"] if f["key"] == "format")
    assert fmt["type"] == "choice"
    assert set(fmt["values"]) == {"html", "text", "markdown"}


def test_catalog_featured_subset():
    """The featured list must be a subset of returned service ids."""
    from arm.notifications.catalog import build_catalog, FEATURED_SERVICES
    # Run against the real apprise package (no mock) to confirm the
    # featured list aligns with what's actually installed.
    catalog = build_catalog()
    service_ids = {s["id"] for s in catalog["services"]}
    for feat in FEATURED_SERVICES:
        assert feat in service_ids, (
            f"featured service {feat!r} not in installed apprise plugins"
        )
