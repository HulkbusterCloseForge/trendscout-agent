# Google OAuth Setup

TrendScout can run without Google by using local Drive/Sheet mocks. For real delivery, provide OAuth credentials with scopes for Drive upload and Sheets append.

## Required Scopes

- `https://www.googleapis.com/auth/drive.file`
- `https://www.googleapis.com/auth/spreadsheets`

## MVP Auth Modes

### Simple dev mode

Set an access token:

```bash
export GOOGLE_ACCESS_TOKEN="ya29..."
export GOOGLE_DRIVE_FOLDER_ID="..."
export GOOGLE_SHEET_ID="..."
```

### Token JSON mode

Create a JSON file containing:

```json
{
  "access_token": "ya29..."
}
```

Then:

```bash
export GOOGLE_TOKEN_JSON=./secrets/google-token.json
```

## Implemented dashboard flow

1. Put your OAuth client file at `secrets/google-oauth-client.json` or set `GOOGLE_OAUTH_CLIENT_SECRET_JSON`.
2. Start the app.
3. Open the dashboard and click **Connect Google**.
4. Complete Google consent.
5. The callback saves `data/google-token.json` unless `GOOGLE_TOKEN_JSON` is set.
6. Configure `google_drive_folder_id` and `google_sheet_id` in the dashboard or `data/config.json`.
7. Future deliveries upload to Drive and append to Sheets when folder/sheet IDs are configured.

The app refreshes expired access tokens when a refresh token is present. The delivery adapter boundary is `deliver_outputs(video_path, run_record, output_dir)`.
