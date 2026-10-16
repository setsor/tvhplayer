"""Safe, opt-in diagnostics. Never print full configuration or stream URLs."""

import os
import re
import sys


_URL_CREDENTIALS = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@"
)
_SECRET_FIELDS = re.compile(
    r"""(?i)(['"]?(?:password|authorization|token|secret|api[_-]?key)['"]?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,}]+)"""
)
_BEARER = re.compile(r"(?i)\bBearer\s+[a-z0-9_+./=-]+")


def redact(value):
    """Redact basic URL credentials, secret dictionary fields and bearer tokens."""
    text = str(value)
    text = _URL_CREDENTIALS.sub(r"\1[credentials]@", text)
    text = _SECRET_FIELDS.sub(r"\1[REDACTED]", text)
    return _BEARER.sub("Bearer [REDACTED]", text)


def debug_print(*args, **kwargs):
    """Diagnostic output is silent unless TVHPLAYER_DEBUG=1 is explicitly set."""
    if os.environ.get("TVHPLAYER_DEBUG", "").lower() not in {"1", "true", "yes"}:
        return
    separator = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    destination = kwargs.pop("file", sys.stderr)
    if kwargs:
        raise TypeError(f"Unsupported debug_print options: {', '.join(kwargs)}")
    message = separator.join(str(a) for a in args)
    destination.write(redact(message) + end)
    destination.flush()


def report_error(message):
    """Show a necessary startup error without exposing embedded credentials."""
    sys.stderr.write(redact(message) + "\n")
    sys.stderr.flush()
