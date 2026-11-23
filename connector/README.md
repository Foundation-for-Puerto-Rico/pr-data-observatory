# Observatory connector for Claude (MCP)

This connector lets Claude read the PR Data Observatory's data. You can then ask Claude in a chat for reports, rankings, municipal profiles and map links. It reads the same public JSON files that `observatory.foundationpr.org` serves. It needs no key and stores no data of its own.

## Tools

| Tool | What it returns |
|---|---|
| `list_domains` | The observatory's fields (domains), in Spanish and English, with how many datasets each one has. |
| `search_datasets` | Datasets that match words in Spanish or English. `has_values=true` marks the datasets that the next three tools can read. |
| `describe_dataset` | The data dictionary entry for a dataset: its plain meaning, definition, method, cautions and sources, plus a link to the dictionary. |
| `get_values` | One year of a dataset for all 78 municipios, ranked, with the Puerto Rico total, margins of error and sources. |
| `get_trend` | Every year of a dataset for one municipio, next to the Puerto Rico total. |
| `municipality_profile` | The latest value of every dataset for one municipio, with its rank. You can filter it by domain. |
| `map_link` | A link that opens the map with up to two datasets shaded, zoomed to a municipio. |

It covers 352 per-municipio datasets: all the `*_series.json` files, the municipio snapshot fields (flood, transit access, tourism places) and the census-block exposure counts. It doesn't read barrio, census tract or point data yet, including the WCRP RVI. `search_datasets` still finds those datasets, and `describe_dataset` explains them.

## Use it on your computer (Claude Desktop or Claude Code)

The only requirement is [uv](https://docs.astral.sh/uv/). It installs the `mcp` package the first time the connector runs.

Claude Code:

```bash
claude mcp add observatorio-pr -- uv run --script /path/to/pr-digital-twin/connector/observatory_mcp.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "observatorio-pr": {
      "command": "uv",
      "args": ["run", "--script", "/path/to/pr-digital-twin/connector/observatory_mcp.py"]
    }
  }
}
```

## Use it for the whole team on claude.ai

The connector is served at:

```text
https://observatory.foundationpr.org/api/mcp
```

To add it for your organization, an organization owner does the following on claude.ai:

1. Open **Settings > Connectors**.
2. Click **Add custom connector**.
3. Enter the name `Observatorio PR` and the URL `https://observatory.foundationpr.org/api/mcp`.
4. Leave the advanced (OAuth) settings empty, and click **Add**.

Members then turn it on from a chat's tools menu. The tools only read public data, so the connector needs no sign-in.

### How it's hosted

The site's Azure Static Web App runs the connector as its managed function (Python 3.11, set in `site/staticwebapp.config.json`). The `observatory/` folder holds the function, which serves the MCP app over stateless streamable HTTP with JSON responses. Each request is a complete exchange, which fits the platform's 45-second request limit. A `GET` returns `405`, because a stateless server has no stream to offer.

The **Publish site** workflow (`.github/workflows/pages.yml`) runs `connector/bundle_data.sh`, which copies the data files that the connector reads into `connector/data/`. It runs the checks against that copy, and then deploys the copy with the site. This means:

- The connector's answers always match the published site, because each site deploy also redeploys the connector with that build's data. You don't need to restart anything.
- A cold start reads about 9 MB from disk instead of fetching 30 files from the site.
- If `observatory_mcp.py` starts reading a new file, add it to the `cp` line in `connector/bundle_data.sh`. The **Tests** workflow runs the same script, so a pull request fails its checks until you do.

To run the function on your computer, install [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local). Put the `connector/data/` copy and the packages from `requirements.txt` in this folder, and then run `func start`. The function serves `http://localhost:7071/api/mcp`.

You can also serve the connector as a plain HTTP server on port 8000, at `/mcp`:

```bash
uv run --script connector/observatory_mcp.py --http --port 8000
```

## Settings

| Variable | Default | Purpose |
|---|---|---|
| `OBSERVATORY_URL` | `https://observatory.foundationpr.org` | The site to read from and link to. |
| `OBSERVATORY_DATA` | (not set) | A local `site/data` folder to read from instead of the site. The hosted function sets it to `connector/data`. |

When the connector reads from the site, it keeps the files in memory while it runs. Restart a local copy after a site build so it picks up new data.

## Check it

```bash
uv run --with "mcp>=2.3,<3" python connector/test_observatory_mcp.py
OBSERVATORY_DATA="" uv run --with "mcp>=2.3,<3" python connector/test_observatory_mcp.py   # against the live site
uv run --with "mcp>=2.3,<3" python connector/test_observatory_mcp.py https://observatory.foundationpr.org/api/mcp   # the hosted connector
```
