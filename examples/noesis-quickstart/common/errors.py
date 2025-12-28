from __future__ import annotations


class QuickstartError(Exception):
    """Base error for quickstart failures."""


class ConfigError(QuickstartError):
    """Bad or missing configuration (env vars, files, etc)."""


class NoesisApiError(QuickstartError):
    """Noēsis API mismatch / missing expected surface."""