"""Backward-compatible settings export.

Prefer ``from app.core.config import settings`` in new code.
"""

from app.core.config import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
