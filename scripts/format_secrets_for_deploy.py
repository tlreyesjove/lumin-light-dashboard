"""
One-time helper for deploying to Streamlit Community Cloud.

Reads your LOCAL credentials/service_account.json and .env, and prints a
ready-to-paste TOML block for Streamlit's Secrets box (Settings -> Secrets
on your deployed app, or the "Advanced settings" on the deploy screen).

This deliberately only ever runs on YOUR machine and prints to YOUR
terminal — the private key never needs to be typed by hand (easy to break
via a copy/paste mistake) or pasted into a chat.

Usage:
    python3 scripts/format_secrets_for_deploy.py
"""

import json
import os

CREDS_PATH = os.path.join(os.path.dirname(__file__), "..", "credentials", "service_account.json")
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def read_sheet_id():
    if not os.path.exists(ENV_PATH):
        return None
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_SHEET_ID"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def main():
    if not os.path.exists(CREDS_PATH):
        raise SystemExit(f"Can't find {CREDS_PATH} — run this from a machine that has it set up locally.")

    with open(CREDS_PATH) as f:
        creds = json.load(f)

    sheet_id = read_sheet_id()
    if not sheet_id:
        raise SystemExit("Couldn't find GOOGLE_SHEET_ID in .env — check it's set there.")

    print("# Paste everything below into Streamlit's Secrets box, then click Save.")
    print(f"GOOGLE_SHEET_ID = {json.dumps(sheet_id)}")
    print()
    print("[gcp_service_account]")
    # json.dumps() on each value produces a quoted, escaped string valid in
    # TOML too (both use the same \n / \" / \\ escaping rules) — so the
    # private key's embedded newlines come out correctly with zero manual
    # re-typing or re-escaping.
    for key, value in creds.items():
        print(f"{key} = {json.dumps(value)}")


if __name__ == "__main__":
    main()
