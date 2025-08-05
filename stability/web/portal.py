"""Compatibility facade for the Web portal entry points.

The full ``WebPortalApplication`` implementation lives in
``stability.web.application``.  Keep this module small so legacy imports such
as ``from stability.web.portal import WebPortalApplication`` continue to work.
"""

from __future__ import annotations

from .application import WebPortalApplication
from .server import serve_web_portal

__all__ = ["WebPortalApplication", "serve_web_portal"]
