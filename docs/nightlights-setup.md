# Night-time lights: set up the NASA login (for the project lead)

The night-time lights harvester (`nightlights.py`) downloads NASA's Black Marble monthly files. NASA lists them openly but asks for a free Earthdata login to download them. This guide covers the four things only a person at FPR can do: make the account, approve LAADS, make a token and save it in GitHub. It takes about 15 minutes.

**Before you start:** HANDOFF decision 75 asks whether the build may use this login. Do these steps once you approve it.

**Keep the token secret.** A token works like a password. Paste it in only two places: the GitHub secret form (step 4) and, if you test on your own computer, your own terminal (step 5). Never paste it into a chat (Claude included), an issue, a pull request, an email or any file in the repository. If it ends up anywhere else, delete it (step 3, "Revoke") and make a new one.

## 1. Make the account

1. Go to https://urs.earthdata.nasa.gov and click **Register**.
2. Use a **shared FPR address** if you can, such as a data or IT mailbox, so the account doesn't depend on one person. Use a personal FPR address only if no shared one exists, and write down in HANDOFF which address you used (the address, not the password).
3. Fill in the form. Choose a username and a strong password, and keep them in FPR's password manager. Reasonable answers for the other fields:
   - Affiliation: **Non-profit**
   - Organization: **Foundation for Puerto Rico**
   - Country: **United States**
   - Study area: **Land Use and Land Cover**, or the closest choice to "economic activity"
   - User type: **Public User**
4. Accept the terms and click **Register for Earthdata Login**.
5. Open the email NASA sends and click the link to confirm the address. The account can't download anything until you confirm it.

## 2. Approve the LAADS DAAC application

LAADS DAAC is the NASA archive that holds the Black Marble files. It only accepts your token after you approve it on your account.

1. Sign in at https://urs.earthdata.nasa.gov.
2. Open **Applications → Authorized Apps** in the top menu.
3. Click **Approve More Applications**.
4. Search for **LAADS**, find **LAADS DAAC** and click **Authorize** (or **Approve**). If it shows terms of use, read and accept them.
5. Check that LAADS DAAC now appears in your **Authorized Apps** list. It may be listed as **LAADS Web**.
6. **Sign in to LAADS once and accept the license for these files.** Go to https://ladsweb.modaps.eosdis.nasa.gov, click **Login** (top right), choose **Earthdata Login** and sign in. Then, in the same browser, open one Black Marble file, for example https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VNP46A3/2012/001/VNP46A3.A2012001.h11v07.002.2025086154536.h5 . LAADS shows a license agreement: accept it. The file (about 55 MB) may then download; you can delete it. Until you do this, LAADS refuses the token and sends the build to its license page (the message shows `…/profiles/licenses/…`). On 2026-11-04 the acceptance took a few minutes to reach the token: if the first check still fails, wait ten minutes and run it again before making a new token. To check without downloading everything, push a tag named `nightlights-diag-<anything>`: the workflow then only reports what LAADS answers for one file (`python nightlights.py --diagnose`; it never prints the token).

## 3. Make a token and note when it expires

1. While signed in, open **Generate Token** in the top menu (https://urs.earthdata.nasa.gov/profile, tab **Generate Token**).
2. Click **Generate Token**. A long code appears with an **expiration date**. Tokens last about **60 days**.
3. Copy the token. Don't save it in a document; go straight to step 4.
4. **Set a renewal reminder now:** put a calendar reminder about **50 days from today** called "Renew NASA Earthdata token (EARTHDATA_TOKEN)". When it comes up, repeat this step and step 4. Earthdata allows two tokens at a time, so make the new one, save it in GitHub, then click **Revoke** on the old one.

## 4. Save the token as a GitHub secret

You need admin rights on the repository.

1. Go to https://github.com/Foundation-for-Puerto-Rico/pr-data-observatory.
2. Click **Settings** (top right of the repository; you need admin rights to see it).
3. In the left menu, open **Secrets and variables → Actions**.
4. On the **Secrets** tab, click **New repository secret**.
5. **Name:** `EARTHDATA_TOKEN` (exactly this, in capitals).
   **Secret:** paste the token.
6. Click **Add secret**.

GitHub never shows a secret again after you save it, and it hides the secret in run logs. To renew it, open the same page, click the pencil next to `EARTHDATA_TOKEN`, paste the new token and click **Update secret**.

## 5. Check that the harvester works

**On GitHub (after the nightly change).** The build only reads the secret once the workflow change in the pull request is approved and merged. Then go to **Actions → Rebuild a data source → Run workflow**, choose `nightlights` and click **Run workflow**. The **Rebuild** step should show lines like these:

```
nightlights: 177 monthly files listed for h11v07 since 2012; 177 to download
  h11v07: 43,925 pixels in a barrio, 3 barrios smaller than a pixel take the pixel under them
  downloading VNP46A3.A2012001.h11v07.002....h5 (70 MB)
  2012-01: Puerto Rico ... nW/cm²/sr, ...% of pixels poor or gap-filled
wrote nightlights_series.json: ... KB
```

The first run downloads every month since January 2012, about 12 GB, and takes an hour or more. Each later run downloads only the new months.

**On your own computer (optional).** In PowerShell, in the repository folder:

```powershell
$s = Read-Host -AsSecureString "Earthdata token"
$env:EARTHDATA_TOKEN = [Net.NetworkCredential]::new('', $s).Password
python nightlights.py --since 2026
```

The token you type isn't shown and stays in that terminal window only; close the window when you're done. `--since 2026` downloads only this year's months (about 0.6 GB) to check that everything works.

**What the messages mean:**

| Message | What it means | What to do |
|---|---|---|
| `EARTHDATA_TOKEN is not set` | The build ran without the token. It changed nothing. | Check the secret's name (step 4), or set the variable in the terminal. |
| `LAADS refused the download (HTTP 303 ...)` | NASA sent the request to its sign-in page. The token has expired, has been revoked, or LAADS isn't approved. | Check step 2, then make a new token (step 3) and update the secret (step 4). |
| `... Puerto Rico ... nW/cm²/sr` lines, then `wrote nightlights_series.json` | It works. | Nothing. |

If anything else goes wrong, send Claude the message, not the token.
