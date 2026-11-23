"""Serves the observatory MCP server at /api/mcp as a Static Web Apps managed function."""

import asyncio
import os

import azure.functions as func
from mcp.server.transport_security import TransportSecuritySettings

# The deploy copies the data files next to the function (.github/workflows/pages.yml), so a cold
# start reads them from disk instead of fetching 30 files from the site.
os.environ.setdefault("OBSERVATORY_DATA", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))

from observatory_mcp import mcp  # noqa: E402

# Stateless JSON: every POST is a whole exchange, which fits the 45-second request limit and a
# function that may run on several instances. The DNS-rebinding check guards servers on a
# private network; this one is public, read-only and takes no credentials, so it's off and
# any Host header (the custom domain, the default *.azurestaticapps.net one) works.
app = mcp.streamable_http_app(
    streamable_http_path="/api/mcp", stateless_http=True, json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
asgi = func.AsgiMiddleware(app)
started = asyncio.Lock()


async def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    if req.method == "GET":  # a stateless server has no stream to offer; the SDK would hold the GET open until the 45-second cutoff
        return func.HttpResponse(status_code=405, headers={"Allow": "POST, DELETE"})
    async with started:  # the MCP session manager runs in the app's lifespan, which Functions doesn't start
        if asgi.lifespan_startup_event is None:
            await asgi.notify_startup()
    return await asgi.handle_async(req, context)
