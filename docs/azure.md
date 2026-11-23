# Hosting on Azure

The observatory is served by Azure Static Web Apps at `https://observatory.foundationpr.org/`. It moved from GitHub Pages in three phases:

1. **The site (this document, done 2026-11-11).** Azure serves the `site/` folder, and the old GitHub Pages address redirects to it.
2. **Large data in Blob Storage.** Static Web Apps holds at most 500 MB for each environment on the Standard plan, and the site grows about 9 MB a week (45 MB on 2026-10-01, 82 MB on 2026-10-28). The large layers (`landuse.geojson`, `places.json`, `flood.geojson`, `roads.bin`) move to Azure Blob Storage, as planned in `docs/proposal-2026-10.md`, section E, item 6.
3. **Simulations.** A Container App that runs scenarios, linked to the site as its backend.

## Resources

| Resource | Name | Notes |
|---|---|---|
| Resource group | `rg-observatory-prod` (East US 2) | Separate from `rg-viewpr-prod`: VIEWPR is internal and on a compliance hold; the observatory is public. |
| Static Web App | `swa-observatory-prod` | Standard plan (SLA, 500 MB for each environment). Not connected to the repository: GitHub Actions deploys it with a token. |

Tags on both: `Workload=Observatory`, `env=prod`, `CostCenter=RBDG-CIH`, and `Program=RBDG-CIH`. The resource group also lists its owners in `Owner`.

## Set up the site (phase 1)

These steps record how the site was set up, for a rebuild or a second environment. IT creates the resource group and the DNS record. You need the Contributor role on the resource group.

1. **Ask IT** to create `rg-observatory-prod` in East US 2 with the tags, and to give you Contributor on it.
2. **Create the Static Web App** without a repository, so that Azure does not commit a workflow to `main` or create a preview environment for every pull request:

   ```bash
   az staticwebapp create -n swa-observatory-prod -g rg-observatory-prod -l eastus2 --sku Standard --tags Workload=Observatory env=prod CostCenter=RBDG-CIH Program=RBDG-CIH
   ```

3. **Give the repository the deployment token.** The pipe sends the token straight into the secret, so no person sees it:

   ```bash
   az staticwebapp secrets list -n swa-observatory-prod -g rg-observatory-prod --query properties.apiKey -o tsv | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN -R Foundation-for-Puerto-Rico/pr-data-observatory
   ```

4. **Publish.** Run **Actions > Publish site > Run workflow**.
5. **Check the Azure address.** Get it with `az staticwebapp show -n swa-observatory-prod -g rg-observatory-prod --query defaultHostname -o tsv`. Open the map, 3D, a knowledge area, the dictionary, and a missing page (the 404 page must show its styles and working links).
6. **Ask IT for the DNS record:** a CNAME from `observatory.foundationpr.org` to the default hostname from step 5.
7. **Add the domain** once the record resolves. Azure issues the TLS certificate:

   ```bash
   az staticwebapp hostname set -n swa-observatory-prod -g rg-observatory-prod --hostname observatory.foundationpr.org
   ```

   The command registers the domain, then fails with `AuthorizationFailed` while it waits, because reading the operation's status needs a role on the subscription. Follow the domain with `az staticwebapp hostname list -n swa-observatory-prod -g rg-observatory-prod` instead: it goes from `Validating` to `Adding` to `Ready` in about 15 minutes. For a few more minutes after `Ready`, some requests still get Azure's default certificate.

## How publishing works

`.github/workflows/pages.yml` runs on every push to `main` that touches `site/`, `connector/`, or the workflow itself. Its one job:

- **`azure`** runs the privacy checks on `places.json` and then uploads `site/` to the Static Web App with the `AZURE_STATIC_WEB_APPS_API_TOKEN` secret. Nothing reaches the site when a check fails.
