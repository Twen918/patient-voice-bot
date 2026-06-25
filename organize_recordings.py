"""
organize_recordings.py - match each recording to its transcript scenario.

The reliable link between a recording and a transcript is the Call SID (the
`CA...` id), which both sides share. This script:

  1. reads every transcripts/*.json to map  call_sid -> (scenario, timestamp)
  2. asks Twilio for each recording's call_sid + duration
  3. renames each recordings/RE*.mp3  ->  <timestamp>_<scenario>_<REsid>.mp3
  4. writes recordings/INDEX.md, a table linking recording <-> scenario <-> call

Safe to run multiple times. Run it AFTER fetch_recordings.py.

Usage:
    python organize_recordings.py
"""
import os
import json
import datetime
from pathlib import Path

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

REC_DIR = Path("recordings")
TR_DIR = Path("transcripts")


def load_transcript_map():
    """call_sid -> {'scenario': str, 'stamp': str} from transcripts/*.json."""
    mapping = {}
    for jf in TR_DIR.glob("*.json"):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  (skipped {jf.name}: {e})")
            continue
        call_sid = data.get("call_sid")
        if not call_sid:
            continue
        # filename looks like 20260624_041650_schedule_basic.json
        stem = jf.stem
        parts = stem.split("_", 2)
        stamp = "_".join(parts[:2]) if len(parts) >= 2 else stem
        mapping[call_sid] = {
            "scenario": data.get("scenario", "unknown"),
            "stamp": stamp,
        }
    return mapping


def safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name)


def main():
    if not REC_DIR.exists():
        print("No recordings/ folder. Run fetch_recordings.py first.")
        return

    tmap = load_transcript_map()
    print(f"Loaded {len(tmap)} transcript(s) with a call_sid.\n")

    client = Client(ACCOUNT_SID, AUTH_TOKEN)

    # Build: recording_sid -> {call_sid, duration} from Twilio.
    rec_info = {}
    for rec in client.recordings.list(limit=200):
        rec_info[rec.sid] = {
            "call_sid": rec.call_sid,
            "duration": rec.duration,
        }

    rows = []
    for mp3 in sorted(REC_DIR.glob("*.mp3")):
        # recording sid is the RE... part of the current filename
        re_sid = mp3.stem.split("_")[-1]  # handles already-renamed files too
        if not re_sid.startswith("RE"):
            re_sid = mp3.stem
        info = rec_info.get(re_sid, {})
        call_sid = info.get("call_sid", "")
        duration = info.get("duration", "?")
        meta = tmap.get(call_sid, {})
        scenario = meta.get("scenario", "unmatched")
        stamp = meta.get("stamp", "")

        # new name: 20260624_041650_schedule_basic_RExxxx.mp3
        prefix = f"{stamp}_" if stamp else ""
        new_name = f"{prefix}{safe(scenario)}_{re_sid}.mp3"
        new_path = REC_DIR / new_name
        if mp3.name != new_name:
            if new_path.exists():
                new_path.unlink()
            mp3.rename(new_path)
            print(f"  {mp3.name}  ->  {new_name}")
        rows.append({
            "file": new_name,
            "scenario": scenario,
            "duration": duration,
            "call_sid": call_sid or "(not found in Twilio)",
        })

    # Write the index table.
    rows.sort(key=lambda r: r["file"])
    lines = [
        "# Recording Index",
        "",
        "Each recording is matched to its transcript scenario by Call SID.",
        f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M}.",
        "",
        "| Recording file | Scenario | Duration (s) | Call SID |",
        "|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['file']}` | {r['scenario']} | {r['duration']} | `{r['call_sid']}` |"
        )
    (REC_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    matched = sum(1 for r in rows if r["scenario"] not in ("unmatched", "unknown"))
    print(f"\nDone. {len(rows)} recording(s), {matched} matched to a scenario.")
    print(f"Wrote {REC_DIR / 'INDEX.md'}")


if __name__ == "__main__":
    main()
