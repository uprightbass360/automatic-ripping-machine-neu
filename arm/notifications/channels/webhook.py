"""Send a rich-payload webhook with optional HMAC-SHA256 signing.

The wire shape is ``OutboundWebhookPayload`` from arm_contracts. When a
shared_secret is provided, the dispatcher computes HMAC-SHA256 over the
canonical JSON body and sends it in ``X-ARM-Signature: sha256=<hex>``.

The error string returned on failure embeds a ``terminal=true|false``
marker so the dispatcher can decide whether to retry. We don't raise
exceptions — the channel boundary keeps them inside.
"""
import hashlib
import hmac
import json
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15.0
_ALLOWED_SCHEMES = {"http", "https"}


def _is_terminal_status(status_code: int) -> bool:
    """4xx (other than 429) is terminal; 5xx and 429 are transient."""
    if status_code == 429:
        return False
    return 400 <= status_code < 500


def send_webhook(
    *,
    url: str,
    payload_dict: dict,
    shared_secret: Optional[str],
    headers: Optional[dict[str, str]],
) -> tuple[bool, str | None]:
    """POST the payload to the given URL.

    :param url: full HTTPS endpoint
    :param payload_dict: JSON-serializable dict (OutboundWebhookPayload)
    :param shared_secret: optional plain-text HMAC key
    :param headers: optional additional static headers
    :returns: ``(True, None)`` on success, ``(False, "<message> terminal=<bool>")``
        on failure. The dispatcher parses the marker.
    """
    # SSRF guard: validate the URL scheme before issuing any request.
    # Rejects file://, gopher://, etc. so a non-http(s) URL can never
    # reach the HTTP client. (Saved channels are operator-controlled and
    # the unsaved-test path additionally resolves/blocks non-public hosts
    # via url_safety.assert_public_http_url().)
    parsed_url = urlparse(url)
    if parsed_url.scheme.lower() not in _ALLOWED_SCHEMES:
        return False, "invalid webhook URL: scheme must be http or https terminal=true"
    if not parsed_url.hostname:
        return False, "invalid webhook URL: missing host terminal=true"

    body_bytes = json.dumps(
        payload_dict, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")

    request_headers: dict[str, str] = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    if shared_secret:
        digest = hmac.new(
            shared_secret.encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()
        request_headers["X-ARM-Signature"] = f"sha256={digest}"

    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            # SSRF note: for saved channels the URL is operator-controlled
            # (from the DB). The only request-controlled caller is the
            # unsaved-config test endpoint, which validates the URL with
            # url_safety.assert_public_http_url() (rejects loopback/private/
            # link-local/reserved hosts) before reaching here. CodeQL cannot
            # model that custom IP allowlist as a sanitizer; py/full-ssrf is
            # suppressed centrally in .github/codeql/codeql-config.yml.
            resp = client.post(
                url, content=body_bytes, headers=request_headers
            )
    except httpx.HTTPError as exc:
        # Network errors, timeouts, etc. — all transient.
        return False, f"network error: {exc} terminal=false"

    if 200 <= resp.status_code < 300:
        return True, None

    terminal = _is_terminal_status(resp.status_code)
    return (
        False,
        f"HTTP {resp.status_code}: "
        f"{resp.text[:200]} terminal={'true' if terminal else 'false'}",
    )
