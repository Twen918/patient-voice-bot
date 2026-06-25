# Architecture

## How it works

The bot places a real outbound phone call and bridges its audio to a language model that
role-plays a patient. `make_call.py` uses the **Twilio** Voice API to dial the test line and
attaches a bidirectional **Media Stream** — a WebSocket carrying the live call audio as 8 kHz
G.711 µ-law. A **FastAPI** server (`server.py`) accepts that stream on `/media-stream` and
opens a second WebSocket to the **OpenAI Realtime API** (`gpt-realtime`), then bridges the two:
the agent's audio is forwarded into the model as input, and the model's spoken audio is sent
back into the call. The model runs as a "patient" defined by a system prompt assembled in
`scenarios.py` (a shared persona plus a per-call goal passed through Twilio as a stream
parameter). Server-side voice-activity detection drives turn-taking, so the patient waits for
the agent to greet it and then responds, rather than talking over it. During the call the
server logs both sides to `transcripts/`, and Twilio records the audio, which
`fetch_recordings.py` downloads as mp3 and `organize_recordings.py` links back to its scenario
by Call SID.

## Key design choices

The central decision was to use a single **speech-to-speech** model (the Realtime API) instead
of stitching together separate speech-to-text, LLM, and text-to-speech stages. The challenge
rejects any submission whose voice conversation isn't lucid, so low latency and natural
turn-taking were the top priority — and one integrated model handles listening, reasoning,
speaking, and barge-in far more naturally than a hand-built pipeline, with far less that can go
wrong. **Twilio** was chosen because it is the standard, well-documented way to reach a real
PSTN number from code, and its Media Streams use G.711 µ-law, which the Realtime API accepts
directly (sent as `audio/pcmu`) so no resampling is needed. Test behavior lives in data, not
code: `scenarios.py` makes each patient persona a one-line goal, which keeps the bot a generic
"realistic caller" and makes covering ten-plus diverse scenarios trivial. Finally, recordings
and transcripts are matched by **Call SID** rather than by timestamp, because Call SID is a
globally unique, unambiguous key — this keeps the evidence behind the bug report verifiable.
Deliberately out of scope: persistent storage, retries, and other production infrastructure,
which the challenge explicitly does not want.
