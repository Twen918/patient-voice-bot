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
records the audio (downloaded as mp3 by `fetch_recordings.py`). The persona and
per-call goals live in `scenarios.py`, so adding a new test case is one line.

**Why this stack:** a single speech-to-speech model (Realtime API) gives the
lowest-latency, most natural conversation, which is the primary grading
criterion. Twilio is the standard, well-documented way to reach a real phone
number from code.

## Files

| File | Purpose |
|------|---------|
| `server.py` | Twilio ↔ OpenAI Realtime audio bridge + transcript logging |
| `make_call.py` | Places one outbound call for a chosen scenario |
| `scenarios.py` | The patient persona and the goal for each test scenario |
| `fetch_recordings.py` | Downloads Twilio call recordings as mp3 |
| `transcripts/` | Saved `.txt` + `.json` transcripts (deliverable) |
| `recordings/` | Saved `.mp3` call recordings (deliverable) |

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

# 3) place a call
python make_call.py schedule_basic
```

Watch terminal 1 for the live transcript. After a few calls:

```bash
python fetch_recordings.py     # pull mp3s into recordings/
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
