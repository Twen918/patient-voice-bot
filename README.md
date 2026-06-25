# Patient Voice Bot — Pretty Good AI Challenge

An automated voice bot that calls the Pretty Good AI test line, role-plays a
patient across a range of scenarios, records and transcribes each call, and
surfaces quality issues in the agent's responses.

## How it works (architecture)

The bot bridges two real-time audio streams. `make_call.py` uses the **Twilio**
API to place an outbound call to the test line; the call's audio is streamed
over a WebSocket (Twilio Media Streams, 8 kHz `g711_ulaw`) to a local **FastAPI**
server (`server.py`). The server pipes that audio to the **OpenAI Realtime API**
(`gpt-realtime`), which plays a "patient" persona — listening to the agent,
deciding what to say, and speaking back — and streams the patient's audio back
into the call. Server-side voice-activity detection handles turn-taking, so the
patient waits for the agent's greeting and responds naturally.

Each call's both-sides transcript is written to `transcripts/`, and Twilio
records the audio (downloaded as mp3 by `fetch_recordings.py`, then renamed and
matched back to its scenario by Call SID with `organize_recordings.py`). The
persona and per-call goals live in `scenarios.py`, so adding a new test case is
one line. `ARCHITECTURE.md` has the full design write-up.

The findings from running this against the test line are in `BUG_REPORT.md`: 11
calls across 10 scenarios surfaced fabricated patient data (a made-up date of
birth on every call, a phantom phone number on refills), a false "appointment
already booked" state that blocks scheduling, stalled loops, and unvalidated
off-hours requests — each citing the transcript where it occurs.

**Why this stack:** a single speech-to-speech model (Realtime API) gives the
lowest-latency, most natural conversation, which is the primary grading
criterion. Twilio is the standard, well-documented way to reach a real phone
number from code.

## Files

| File | Purpose |
|------|---------|
| `server.py` | Twilio ↔ OpenAI Realtime audio bridge + transcript logging |
| `make_call.py` | Places one outbound call for a chosen scenario |
| `scenarios.py` | The patient persona and the goal for each of the 10 test scenarios |
| `fetch_recordings.py` | Downloads Twilio call recordings as mp3 |
| `organize_recordings.py` | Renames each mp3 and matches it to its scenario by Call SID, writing `recordings/INDEX.md` |
| `BUG_REPORT.md` | The findings — 11 bugs ranked by severity, each citing a transcript (deliverable) |
| `ARCHITECTURE.md` | How the audio bridge works and why this stack (deliverable) |
| `transcripts/` | Saved `.txt` + `.json` transcripts, one per call (deliverable) |
| `recordings/` | Saved `.mp3` recordings + `INDEX.md` mapping each to a scenario (deliverable) |

## Setup

1. **Python env**
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Accounts / keys**
   - OpenAI API key with Realtime access → put in `.env`
   - Twilio account (paid — see Cost note), buy one voice-capable number
   - [ngrok](https://ngrok.com) to expose your local server
3. **Configure**
   ```bash
   cp .env.example .env
   # fill in OPENAI_API_KEY, TWILIO_* , TWILIO_FROM_NUMBER
   ```

## Run

In three terminals:

```bash
# 1) start the bridge server
uvicorn server:app --port 6060

# 2) expose it publicly, then copy the host into .env as PUBLIC_HOST
ngrok http 6060          # e.g. PUBLIC_HOST=abc123.ngrok-free.app

# 3) place a call (any scenario key from scenarios.py)
python make_call.py schedule_basic
```

The 10 scenario keys are `schedule_basic`, `reschedule`, `cancel`,
`refill_request`, `office_hours`, `insurance_question`, `location_question`,
`edge_vague`, `edge_interruptions`, and `edge_offhours_request`.

Watch terminal 1 for the live transcript. After a batch of calls:

```bash
python fetch_recordings.py       # pull mp3s into recordings/
python organize_recordings.py    # rename + match each mp3 to its scenario (writes INDEX.md)
```

> **Rehearse first.** Before calling the real test line, run
> `python make_call.py schedule_basic --to +1YOURCELL` and pick up — confirm the
> patient sounds natural and turn-taking is sane. Voice quality is graded before
> anything else.

## Cost note

Successful submissions typically cost under ~$20 total. Twilio trial accounts
can only call verified numbers, so a small top-up is needed to call the test
line; a US number is ~$1/mo plus ~$0.01–0.02/min. OpenAI Realtime audio is
billed per minute — keep test calls short and check current pricing. Do a couple
of short calls before a full batch.

## Notes / things you may need to adjust

- `websockets` v12+ uses `additional_headers=`; older versions use `extra_headers=`.
- If the `OpenAI-Beta` header errors on a newer Realtime build, remove it.
- Event names differ slightly between Realtime beta and GA — `server.py` handles
  both `response.audio.delta` and `response.output_audio.delta`.
- Reference implementation to cross-check the audio bridge:
  Twilio's official "Outbound calls with Python + OpenAI Realtime API" tutorial.
