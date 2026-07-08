"""FBI Crime Data Explorer MCP Server."""

import os

from fastmcp import FastMCP
from fastmcp.server.middleware.caching import (
    CallToolSettings,
    ResponseCachingMiddleware,
)
from key_value.aio.stores.filetree import (
    FileTreeStore,
    FileTreeV1CollectionSanitizationStrategy,
    FileTreeV1KeySanitizationStrategy,
)
from starlette.requests import Request
from starlette.responses import JSONResponse

from .api_client import app_lifespan
from .constants import CACHE_DIR
from .spillover import ResponseSpilloverMiddleware

# Upstream ships stdio-only. Added here: an optional bearer-token gate so
# this can run as a remote streamable-HTTP MCP connector (e.g. Zenlytic's
# MCP Connectors), which require a publicly reachable HTTPS endpoint that
# stdio can't serve. StaticTokenVerifier is a single shared secret — fine
# for a small trusted group hitting one server, not a substitute for
# per-user OAuth if this ever needs per-caller revocation.
_auth = None
_mcp_auth_token = os.environ.get("MCP_AUTH_TOKEN", "").strip()
if _mcp_auth_token:
    from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

    _auth = StaticTokenVerifier(tokens={_mcp_auth_token: {"client_id": "shared"}})

mcp = FastMCP(
    "FBI Crime Data Explorer",
    instructions=(
        "Query FBI crime statistics from the Crime Data Explorer API. "
        "Data includes crime trends, NIBRS incidents, arrests, hate crimes, "
        "expanded homicide/property data, police employment, LEOKA, LESDC, "
        "and use of force. Use get_reference_data to look up valid offense codes, "
        "bias codes, and state abbreviations. Most date parameters use mm-yyyy format "
        "(e.g., '01-2020'), except police employment and trends which use yyyy format."
    ),
    lifespan=app_lifespan,
    auth=_auth,
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Unauthenticated health probe for container orchestration (e.g. Railway)."""
    return JSONResponse({"status": "ok", "service": "fbi-crime-data-mcp"})

# Import tool modules to register them with the server
from .tools import (  # noqa: E402, F401
    agency,
    arrests,
    cache,
    employment,
    hate_crime,
    homepage,
    homicide,
    leoka,
    lesdc,
    nibrs,
    nibrs_estimation,
    property_data,
    reference,
    spillover_reader,
    summarized,
    trends,
    use_of_force,
)

# --- Response caching with tiered TTLs ---
_cache_dir = CACHE_DIR
_cache_dir.mkdir(parents=True, exist_ok=True)

_cache_store = FileTreeStore(
    data_directory=_cache_dir,
    key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(_cache_dir),
    collection_sanitization_strategy=FileTreeV1CollectionSanitizationStrategy(_cache_dir),
)

_TTL_90_DAYS = 90 * 24 * 3600
_TTL_30_DAYS = 30 * 24 * 3600
_TTL_1_DAY = 24 * 3600

# Long TTL (90 days) — summaries, trends, reference data (rarely changes)
mcp.add_middleware(
    ResponseCachingMiddleware(
        cache_storage=_cache_store,
        call_tool_settings=CallToolSettings(
            ttl=_TTL_90_DAYS,
            included_tools=[
                "get_summarized_crime_data",
                "get_crime_trends",
                "get_reference_data",
                "get_nibrs_estimation",
            ],
        ),
    )
)

# Short TTL (30 days) — agency lookups, granular incident data
mcp.add_middleware(
    ResponseCachingMiddleware(
        cache_storage=_cache_store,
        call_tool_settings=CallToolSettings(
            ttl=_TTL_30_DAYS,
            included_tools=[
                "lookup_agency",
                "get_nibrs_data",
                "get_arrest_data",
                "get_hate_crime_data",
                "get_expanded_homicide_data",
                "get_expanded_property_data",
                "get_police_employment",
                "get_leoka_data",
                "get_lesdc_data",
                "get_use_of_force_data",
            ],
        ),
    )
)

# Daily TTL (1 day) — homepage freshness data (refresh dates change frequently)
mcp.add_middleware(
    ResponseCachingMiddleware(
        cache_storage=_cache_store,
        call_tool_settings=CallToolSettings(
            ttl=_TTL_1_DAY,
            included_tools=[
                "get_cde_homepage_summary",
            ],
        ),
    )
)

# Spillover: save oversized tool responses to disk instead of truncating
mcp.add_middleware(ResponseSpilloverMiddleware())


def main():
    """Entry point for the MCP server. TRANSPORT=http for a remote connector
    (default stdio matches upstream, for local clients like Claude Desktop/Code)."""
    if os.environ.get("TRANSPORT") == "http":
        if _auth is None:
            import logging

            logging.getLogger(__name__).warning(
                "MCP_AUTH_TOKEN is not set — /mcp is unauthenticated. "
                "Set it before exposing this server publicly."
            )
        port = int(os.environ.get("PORT", "8000"))
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
