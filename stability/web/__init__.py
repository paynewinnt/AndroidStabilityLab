"""Minimal dependency-free Web portal for the V3 main entry."""

from .application import WebPortalApplication
from .server import serve_web_portal

__all__ = ["WebPortalApplication", "serve_web_portal"]
