"""User-Agent sent to data.gouv.fr services for identification and support."""

from importlib.metadata import version

USER_AGENT = f"datagouv-mcp/{version('datagouv-mcp')}"
