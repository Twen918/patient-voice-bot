"""
make_call.py - place one outbound test call and bridge its audio to server.py.

The call is created with inline TwiML that opens a bidirectional <Stream> to your
ngrok URL, and passes the chosen scenario through as a <Parameter>. Recording is
enabled so you get an mp3 of the conversation for the deliverables.

Usage:
    python make_call.py schedule_basic
    python make_call.py refill_request --to +1YOURCELL   # rehearse on your own phone first!

Tip: before burning calls on the real test line, set --to to YOUR OWN phone and
listen to whether the "patient" sounds natural. Fix that first - it's the #1
thing that gets graded.
"""
import os
import sys
import argparse

from dotenv import load_dotenv
from twilio.rest import Client

from scenarios import SCENARIOS

load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
TARGET_NUMBER = os.getenv("TARGET_NUMBER", "+18054398008")
PUBLIC_HOST = os.getenv("PUBLIC_HOST")  # ngrok host only, e.g. abc123.ngrok-free.app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=sorted(SCENARIOS.keys()))
    ap.add_argument("--to", default=TARGET_NUMBER,
                    help="override the number to call (use your own phone to rehearse)")
    args = ap.parse_args()

    if not PUBLIC_HOST:
        sys.exit("ERROR: set PUBLIC_HOST in .env to your ngrok host "
                 "(e.g. abc123.ngrok-free.app, no https://)")
    if not all([ACCOUNT_SID, AUTH_TOKEN, FROM_NUMBER]):
        sys.exit("ERROR: missing Twilio credentials in .env")

    stream_url = f"wss://{PUBLIC_HOST}/media-stream"
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        f'<Stream url="{stream_url}">'
        f'<Parameter name="scenario" value="{args.scenario}" />'
        "</Stream>"
        "</Connect></Response>"
    )

    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    call = client.calls.create(
        to=args.to,
        from_=FROM_NUMBER,
        twiml=twiml,
        record=True,
        recording_channels="dual",  # separate channels for agent vs patient
        time_limit=240,             # hard stop so a call can never run away
    )
    print(f"Call placed: {call.sid}")
    print(f"  scenario = {args.scenario}")
    print(f"  to       = {args.to}")
    print("Watch the server window for the live transcript.")
    print("After the call ends, run:  python fetch_recordings.py")


if __name__ == "__main__":
    main()
