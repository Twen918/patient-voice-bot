# Bug Report — Pretty Good AI Voice Agent

**Tester:** Yiwen Tan
**Method:** An automated "patient" voice bot (Twilio + OpenAI Realtime) placed 11+ calls
to the test line (+1‑805‑439‑8008) across 10 scenarios: scheduling, rescheduling,
cancellation, medication refills, office‑hours / insurance / location questions, and
three edge cases (vague symptoms, interruptions/corrections, an off‑hours request).
Each call's audio and a both‑sides transcript are in `recordings/` and `transcripts/`
(matched by Call SID in `recordings/INDEX.md`).

**How to read this:** Bugs are ordered by severity. Each cites the transcript file and the
exchange where it occurs; the matching audio is in `recordings/` under the same scenario name.

**Confidence note (important):** I separate behavior I'm confident is the *agent's* (consistent,
reproducible, semantically meaningful) from a few one‑off oddities that may partly be artifacts of
*my own* speech‑to‑text on 8 kHz phone audio. The high‑severity bugs below were all reproduced
across multiple independent calls, so they are not transcription noise.

---

## High severity

### Bug 1 — Agent fabricates the patient's date of birth on every call
**Severity:** High
**Reproducibility:** 100% — occurs in all 11 calls.
**Where:** e.g. `20260624_183143_reschedule.txt`, `20260624_183602_cancel.txt`,
`20260624_185014_insurance_question.txt` (and every other transcript).
**Details:** When creating the "demo patient profile," the agent asks only for first and last
name, then states a birth date the caller never provided: *"Your patient profile is set up and
your date of birth is July 4, 2000."* The same fabricated date (July 4, 2000) appears in every
single call. In a healthcare setting, date of birth is a primary identity/record‑matching field;
inventing it risks attaching actions (appointments, refills) to the wrong patient record. The
agent should either ask for the DOB or leave it blank — never invent one. In several calls the
caller corrects it to March 14, 1992, and the agent acknowledges the correction, confirming the
original value was fabricated rather than retrieved.

### Bug 2 — Agent hallucinates a pre‑existing appointment and then refuses to book
**Severity:** High
**Reproducibility:** High — `20260624_181636_schedule_basic.txt`,
`20260624_191614_edge_interruptions.txt`, `20260624_191927_edge_offhours_request.txt`.
**Details:** For a brand‑new demo profile with no booking, the agent claims one already exists:
*"It looks like you already have a routine checkup booked … so I can't schedule another one right
now,"* then either loops or offers to transfer. This blocks the agent's core function
(scheduling). In the off‑hours call it derails the entire interaction — the caller asks to book
Sunday 10 a.m., and instead of either booking or explaining hours, the agent repeats *"you already
have a general office visit booked"* and routes to a human. Expected: for a profile with no
appointment, the agent should proceed to schedule.

### Bug 3 — Agent fabricates the patient's phone number before it is provided
**Severity:** High
**Reproducibility:** Both refill calls — `20260624_183930_refill_request.txt`,
`20260624_184315_refill_request.txt`.
**Details:** During a refill, before the caller gives any number, the agent recites a specific
callback number — *"I have your callback number as 951‑636‑8881 … Is that correct?"* — and asks
the caller to confirm it. Same fabrication pattern as the DOB bug, but for the contact number used
to reach a patient about medication. Confirming an invented number as if it were on file is risky;
the agent should ask for the number rather than assert one.

---

## Medium severity

### Bug 4 — Scheduling stalls in an endless "I'll get those times for you" loop
**Severity:** Medium–High
**Where:** `20260624_181636_schedule_basic.txt` (also seen in an earlier `schedule_basic` run).
**Details:** After agreeing to look up morning slots, the agent repeats variations of *"I'll have
those Tuesday morning times for you,"* *"one moment,"* and *"thanks for your patience"* indefinitely
without ever returning an actual time, until the call hits its limit. The booking never completes.
Expected: return concrete slots within a turn or two, or say none are available.

### Bug 5 — Agent re‑asks a question the caller already answered
**Severity:** Medium
**Where:** `20260624_184315_refill_request.txt`.
**Details:** The caller answers *"about two days left"* to "How many days of lisinopril do you have
left?" — and the agent asks the same question three separate times, never registering the answer.
This pairs with the looping behavior in Bug 4: the agent does not retain or act on information the
caller has already given.

### Bug 6 — Provider and medication names are rendered inconsistently
**Severity:** Medium
**Where:** doctor name in `20260624_183602_cancel.txt` and `20260624_183143_reschedule.txt`;
medication name in `20260624_184315_refill_request.txt`.
**Details:** The same doctor is voiced as "Zbigniew Lukoski," "Zbigniew Bukowski,"
"Zigney‑Lukosky," and "Zygmunt Julekowski" — sometimes more than one variant within a single call.
The medication is rendered "lisinopril," "Lysinopril," and "licinapril." Garbled drug and provider
names in a medical context undermine trust and could cause real confusion about who/what was booked
or prescribed. (Caveat: some variance may be the agent's text‑to‑speech; either way it is what the
caller hears.)

### Bug 7 — General questions are gated behind PII / profile creation
**Severity:** Medium (UX / privacy)
**Where:** `20260624_184557_office_hours.txt`, `20260624_185014_insurance_question.txt`,
`20260624_185923_location_question.txt`, `20260624_191235_edge_vague.txt`.
**Details:** A caller simply asking "What are your hours?" or "Do you accept Aetna?" is first pushed
through "create a demo patient profile" (name, then a fabricated DOB) before getting an answer.
Public information shouldn't require collecting personal data. Office hours, address, and
insurance‑acceptance questions should be answerable without a profile.

### Bug 8 — Insurance flow gives contradictory answers and over‑requests sensitive data
**Severity:** Medium
**Where:** `20260624_185014_insurance_question.txt`.
**Details:** Asked whether Aetna PPO is accepted for a new‑patient visit, the agent says *"Aetna PPO
is accepted here,"* then *"coverage depends on your specific plan,"* then escalates: member ID,
then state, then *"could you read the claims mailing address or P.O. box from the back of your
insurance card?"* — without ever giving a clear yes/no on new‑patient coverage. The repeated
asks for card details are excessive for a simple acceptance question and never resolve it.

### Bug 9 — Off‑hours request is never validated against the practice's own hours
**Severity:** Medium
**Where:** `20260624_191927_edge_offhours_request.txt` (compare stated hours in
`20260624_184557_office_hours.txt`: Mon–Fri, closed weekends).
**Details:** The caller asks to book **Sunday** 10 a.m. The agent replies *"Let me check for
openings on Sunday at 10 a.m."* and never flags that the practice is closed on weekends; the
request is instead swallowed by the false "already booked" bug (Bug 2). Expected: recognize Sunday
is outside operating hours and offer the next available weekday — this is exactly the failure class
in the challenge's example bug report.

---

## Lower severity / lower confidence

### Bug 10 — Spurious, unprofessional filler utterances
**Severity:** Low
**Where:** `20260624_183930_refill_request.txt` ("Thank you for watching."; "create a **devil**
patient profile"), `20260624_191235_edge_vague.txt` (ends the call with "Namaste."),
`20260624_191614_edge_interruptions.txt` (ends abruptly: "Hello, you've reached the pretty good AI
test line. Goodbye.").
**Details:** Occasional out‑of‑place phrases break the professional tone expected of a medical
line. (Confidence: lower — some of these single‑word oddities may be my speech‑to‑text mis‑hearing
the agent's audio rather than the agent's true output. Listed for completeness; verify against the
recordings.)

### Bug 11 — Non‑English / language‑switching handling breaks the conversation
**Severity:** Medium (pending transcript)
**Where:** recording `unmatched_REba6b91223b25037586a7095e37da5649.mp3` (transcript to be attached).
**Details:** The line opens with a Spanish prompt ("Para Español, oprima el 2"). On a call where the
caller spoke Spanish, the agent fell into a tight loop — repeating *"I just need your first and last
name"* five or more times — and could not advance, mixing English and Spanish without resolving the
language. Expected: detect the caller's language and either continue in it or hand off cleanly.
(Evidence: see the recording above; transcript produced separately — see README.)

---

## Summary

The most serious and consistent issues are **fabricated patient data** (date of birth on every
call, phone number on refills) and a **false "appointment already booked" state** that blocks the
core scheduling function. Together these would cause real problems in production: actions attached
to invented identifiers, and patients unable to book. The medium‑severity issues (stalled loops,
unanswered questions, inconsistent drug/provider names, PII‑gated FAQs, and unvalidated off‑hours
requests) point to weak retention of conversation state and missing validation against the
practice's own data (hours, existing appointments).
