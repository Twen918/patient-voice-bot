"""
server.py - Twilio <-> OpenAI Realtime bridge.

Twilio connects to the /media-stream WebSocket during an outbound call and
streams the live call audio (the Pretty Good AI agent's voice). We forward that
audio to the OpenAI Realtime API, which plays a "patient" persona, and stream
the patient's spoken replies back into the call. A both-sides transcript is
saved to transcripts/.

Run:  uvicorn server:app --port 6060
(then expose it with ngrok and place a call with make_call.py)
"""
import os
import json
import asyncio
import datetime
from pathlib import Path

import websockets
from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from dotenv import load_dotenv

from scenarios import build_instructions

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime")
VOICE = os.getenv("PATIENT_VOICE", "alloy")

TRANSCRIPTS_DIR = Path("transcripts")
TRANSCRIPTS_DIR.mkdir(exist_ok=True)

app = FastAPI()


@app.get("/")
async def health():
    return {"status": "ok"}


@app.websocket("/media-stream")
async def media_stream(twilio_ws: WebSocket):
    await twilio_ws.accept()
    print(">> Twilio connected to /media-stream")

    stream_sid = None
    call_sid = None
    scenario_key = "schedule_basic"

    # 1) Wait for Twilio's 'start' event so we learn the streamSid + scenario.
    while True:
        msg = json.loads(await twilio_ws.receive_text())
        if msg.get("event") == "start":
            stream_sid = msg["start"]["streamSid"]
            call_sid = msg["start"].get("callSid")
            params = msg["start"].get("customParameters", {}) or {}
            scenario_key = params.get("scenario", scenario_key)
            print(f">> Call started. scenario={scenario_key} streamSid={stream_sid}")
            break

    instructions = build_instructions(scenario_key)
    transcript = []  # list of (speaker, text)

    # 2) Connect to the OpenAI Realtime API.
    url = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    # NOTE: older `websockets` versions use extra_headers= instead of additional_headers=
    async with websockets.connect(url, additional_headers=headers) as openai_ws:
        # Configure the session (OpenAI Realtime GA shape). Twilio media is 8kHz
        # G.711 u-law, which the GA API calls "audio/pcmu". server_vad lets the
        # model decide when a turn ends (natural turn-taking).
        await openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": REALTIME_MODEL,
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcmu"},
                        "turn_detection": {"type": "server_vad"},
                        # Captures the AGENT's words for the live transcript.
                        # If you ever get an invalid_request error that mentions
                        # "transcription", delete the next line and rerun.
                        "transcription": {"model": "whisper-1"},
                    },
                    "output": {
                        "format": {"type": "audio/pcmu"},
                        "voice": VOICE,
                    },
                },
                "instructions": instructions,
            },
        }))
        # We intentionally do NOT trigger a first response: the PGAI agent greets
        # first, and server VAD makes our patient reply after it hears that greeting.

        async def twilio_to_openai():
            """Forward call audio (agent's voice) from Twilio into OpenAI."""
            try:
                async for raw in twilio_ws.iter_text():
                    data = json.loads(raw)
                    event = data.get("event")
                    if event == "media":
                        await openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": data["media"]["payload"],
                        }))
                    elif event == "stop":
                        print(">> Twilio stream stopped.")
                        break
            except WebSocketDisconnect:
                print(">> Twilio disconnected.")
            finally:
                await openai_ws.close()

        async def openai_to_twilio():
            """Forward the patient's audio + capture both sides of the transcript."""
            async for raw in openai_ws:
                event = json.loads(raw)
                etype = event.get("type", "")

                # Patient audio -> back into the phone call.
                # (handle both beta and GA event names)
                if etype in ("response.audio.delta", "response.output_audio.delta"):
                    delta = event.get("delta")
                    if delta and stream_sid:
                        await twilio_ws.send_text(json.dumps({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": delta},
                        }))

                # The AGENT's words (transcription of the audio we sent in).
                elif etype == "conversation.item.input_audio_transcription.completed":
                    text = (event.get("transcript") or "").strip()
                    if text:
                        transcript.append(("AGENT", text))
                        print(f"AGENT  : {text}")

                # Our PATIENT's words (transcript of what we said).
                elif etype in ("response.audio_transcript.done",
                               "response.output_audio_transcript.done"):
                    text = (event.get("transcript") or "").strip()
                    if text:
                        transcript.append(("PATIENT", text))
                        print(f"PATIENT: {text}")

                # Barge-in: if the agent starts talking, stop our queued audio so
                # we don't talk over it.
                elif etype == "input_audio_buffer.speech_started":
                    if stream_sid:
                        await twilio_ws.send_text(json.dumps({
                            "event": "clear", "streamSid": stream_sid,
                        }))

                elif etype == "error":
                    print(f"!! OpenAI error: {event.get('error')}")

        try:
            await asyncio.gather(twilio_to_openai(), openai_to_twilio())
        except Exception as e:
            print(f"!! bridge error: {e}")
        finally:
            _save_transcript(scenario_key, call_sid, transcript)


def _save_transcript(scenario_key, call_sid, transcript):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = TRANSCRIPTS_DIR / f"{ts}_{scenario_key}"
    with open(f"{base}.txt", "w", encoding="utf-8") as f:
        f.write(f"# scenario: {scenario_key}   call_sid: {call_sid}\n\n")
        for speaker, text in transcript:
            f.write(f"{speaker}: {text}\n")
    with open(f"{base}.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "scenario": scenario_key,
                "call_sid": call_sid,
                "turns": [{"speaker": s, "text": t} for s, t in transcript],
            },
            f, indent=2,
        )
    print(f">> Saved transcript -> {base}.txt ({len(transcript)} turns)")
