"""Minimal dependency-free Web portal for the V3 main entry."""

from .application import WebPortalApplication
from .server import create_web_portal_server, serve_web_portal

__all__ = ["WebPortalApplication", "create_web_portal_server", "serve_web_portal"]
