"""
fetch_recordings.py - download your Twilio call recordings as mp3 into recordings/.

Run this after you've made some calls. Twilio stores recordings server-side; this
pulls them down so you can submit the audio (the challenge requires mp3 or ogg).

Usage:
    python fetch_recordings.py
"""
import os
import base64
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

OUT = Path("recordings")
OUT.mkdir(exist_ok=True)


def main():
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    token = base64.b64encode(f"{ACCOUNT_SID}:{AUTH_TOKEN}".encode()).decode()

    count = 0
    for rec in client.recordings.list(limit=100):
        dest = OUT / f"{rec.sid}.mp3"
        if dest.exists():
            continue
        mp3_url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}"
            f"/Recordings/{rec.sid}.mp3"
        )
        req = urllib.request.Request(mp3_url)
        req.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
            f.write(r.read())
        count += 1
        print(f"Saved {dest}  (call {rec.call_sid}, {rec.duration}s)")

    print(f"Done. {count} new recording(s) downloaded to {OUT}/")


if __name__ == "__main__":
    main()
