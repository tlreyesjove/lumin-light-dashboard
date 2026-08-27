# Setup guide

Full instructions for connecting this project to your own Google Sheet and
deploying it to Streamlit Community Cloud.

## 1. Create the Google Sheet

- Go to [sheets.google.com](https://sheets.google.com) and create a new
  blank sheet.
- Copy the ID from its URL:
  `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

## 2. Create a Google Cloud project

- Go to [console.cloud.google.com](https://console.cloud.google.com).
- Top-left project dropdown → **New Project** → name it → **Create**.
- Make sure the new project is selected.

## 3. Enable the Google Sheets API

- Search "Google Sheets API" in the top search bar → open it → **Enable**.

## 4. Create a service account

A service account is a non-human "robot" login the app uses to read the
Sheet, instead of a personal Google account.

- Search "Service Accounts" → **Create Service Account** → name it → **Create
  and Continue** → skip the optional role/access screens → **Done**.
- Open the service account → **Keys** tab → **Add Key** → **Create new key**
  → type **JSON** → **Create**. A `.json` file downloads.
- Move that file into `credentials/` and rename it to
  `service_account.json`.

## 5. Share the Sheet with the service account

- On the service account's details page, copy its email address (looks like
  `name@project-id.iam.gserviceaccount.com`).
- Open your Sheet → **Share** → paste that email → give it **Editor**
  access.

## 6. Configure local environment variables

- Copy `.env.example` to `.env`.
- Set `GOOGLE_SHEET_ID` to the ID from step 1.
- Leave `GOOGLE_SERVICE_ACCOUNT_FILE` as-is if you followed step 4 exactly.

## 7. Push data to the Sheet

```bash
python3 scripts/push_to_sheets.py
```

Four tabs should appear: Sales, Finance, Inventory, AR.

`.env` and `credentials/service_account.json` are both gitignored — they're
specific to your Google account and never get committed.

## Deploying to Streamlit Community Cloud

Streamlit Cloud has no local filesystem, so credentials are supplied through
its **Secrets** mechanism instead of the `credentials/service_account.json`
file used locally.

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, click **New app**, pick this repo, set the main file path to
   `app.py`.
3. Before deploying, open **Advanced settings** (or later, **Settings →
   Secrets**) and paste in:

   ```toml
   GOOGLE_SHEET_ID = "your-sheet-id-here"

   [gcp_service_account]
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "...@....iam.gserviceaccount.com"
   client_id = "..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "..."
   ```

   Every value comes directly from your local `credentials/service_account.json`
   — same fields, JSON there and TOML here. The Sheet must already be shared
   with that service account's email as an Editor (step 5 above).

4. Click **Deploy**.

`scripts/format_secrets_for_deploy.py` will generate this block for you from
your local `.env` and `credentials/service_account.json`:

```bash
python3 scripts/format_secrets_for_deploy.py
```
