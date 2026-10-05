# Transcription — layer 1

Everything downstream (cuts, captions, effects on words) needs **word-level timestamps** in
Hebrew. This file: how the engine is chosen, the cloud options, and how to talk the member
through getting an API key.

## Contents
1. Why word-level, and why ivrit.ai
2. How the studio chooses (hardware rule)
3. Local engine details
4. Cloud engines — comparison
5. Getting an API key (member-facing steps)
6. Accuracy notes and fixes
7. Privacy

---

## 1. Why word-level, and why ivrit.ai

Phrase/SRT transcripts lose the sub-second timing that cutting and karaoke captions need, so
the studio always keeps every word with its start/end. The best Hebrew model we know is
**ivrit.ai's fine-tune of Whisper large-v3-turbo** (`ivrit-ai/whisper-large-v3-turbo-ct2`,
Apache 2.0, pinned to one snapshot — snapshots differ in quality). On ivrit.ai's benchmark it
scores ~5.3% WER on conversational Hebrew versus 20% for ElevenLabs Scribe v1, which silently
drops 10–25% of words — exactly the fillers and false starts an editor needs to see.

## 2. How the studio chooses

`studio doctor` (check_system.py) reads the hardware and recommends:

| Machine | Engine | Typical speed |
|---|---|---|
| NVIDIA GPU with ≥ 4 GB VRAM (Windows) | local, GPU float16 | 15–60× realtime |
| Apple Silicon, ≥ 16 GB RAM | local, CPU float32 batched | ~6× realtime (M4 measured) |
| Apple Silicon, 8 GB | local, int8 | ~1.5–2.5× |
| Intel/AMD PC or Intel Mac, ≥ 8 GB RAM, ≥ 6 cores | local, int8 (fine for reels; slow for long videos) | ~1–2.5× |
| weaker, < 3 GB free disk, or Windows on ARM | cloud | — |

"6× realtime" = a 60 s clip in 10 s. After the first real clip, check the printed speed:
if it's under ~0.7× or the whole project would take more than ~15 minutes, offer the cloud
path with a price. The member can always override: privacy/offline → local; "fast, cost
doesn't matter" → cloud. Change the default with `studio setup --step transcription --engine <x>`
or per run with `studio transcribe <name> --engine <x>`.

## 3. Local engine details

- faster-whisper 1.2.1 + ctranslate2 ≥ 4.6.3 (no cuDNN needed on NVIDIA; only cuBLAS, which
  the studio adds automatically — ~550 MB extra, once).
- Model download ~1.7 GB into the studio's `.cache/hf` (never into the user profile — Hebrew
  Windows usernames break model loading).
- First run in a session also loads the model (10–30 s).
- `--prompt "Claude Code, Remotion, סקיל"` biases spelling of names; it helps Hebrew words but
  usually NOT English brand names → `fixes` in plan.json remain necessary.
- Word start times tend to be ~0.1 s early; the cut planner pads for this and uses the audio
  itself to find pauses.

## 4. Cloud engines — comparison (checked 2026-09)

| Engine (`--engine`) | Hebrew quality | Word times | Price / audio hour | Signup |
|---|---|---|---|---|
| `soniox` | best API on the ivrit.ai leaderboard (≈ local model) | yes | ~$0.10 | card needed (no free credit) |
| `deepgram` (Nova-3) | good on clean speech, weaker on noisy/broadcast | yes | ~$0.26 — **$200 free credit, no card** | easiest real option |
| `groq` (Whisper large-v3) | ~2× the errors of ivrit.ai | yes | free tier (25 MB/file ≈ 2 h as Opus) | no card |
| `openai` (whisper-1) | like vanilla Whisper large-v2 | yes | ~$0.36 | card + prepaid credit |

**Why not "GPT-4o transcribe" / the newest OpenAI models?** They return no word timestamps
(OpenAI's own docs: use whisper-1 when you need them) — useless for editing. Google Chirp 3
likewise has no word timestamps for Hebrew; Gemini's timestamps are generated text, not
acoustic. ElevenLabs Scribe v2 is unbenchmarked on Hebrew (v1 dropped words) — not offered.

Recommendation: weak computer + no card → **deepgram**; best accuracy and willing to add a
card → **soniox**; just trying it out → **groq**.

Free no-install alternative for a one-off: the member can upload to transcribe.ivrit.ai (web,
Google login, free weekly quota) — but the studio can't read its output automatically.

## 5. Getting an API key (say this to the member, one step at a time)

Keys live in `api-keys.txt` in the studio folder (a plain text file the setup created, with a
line ready for each service). The member pastes the key there themselves, so it stays on their
computer and never passes through the chat. Offer to open the file for them (Mac:
`open -e api-keys.txt`; Windows: `notepad api-keys.txt`). The studio's tools read it directly;
you don't need to open or print it.

**Deepgram**
1. Go to console.deepgram.com and sign up (Google login works). You get $200 of free credit.
2. In the dashboard: "API Keys" → "Create a New API Key" → give it any name → create.
3. Copy the key (shown once).
4. In `api-keys.txt`, on the line `# DEEPGRAM_API_KEY=`: delete the `#` and paste the key after
   the `=`. Save.
5. Tell me "done".

**Soniox** — soniox.com → sign up → console → add a payment method → API keys → create →
`api-keys.txt`: `SONIOX_API_KEY=...`

**Groq** — console.groq.com → sign in → API Keys → Create → `api-keys.txt`: `GROQ_API_KEY=...`

**OpenAI** — platform.openai.com → Billing (add credit) → API keys → Create → `api-keys.txt`:
`OPENAI_API_KEY=...`

Then: `studio setup --step transcription --engine deepgram` (records the choice and checks
the key is there).

## 6. Accuracy notes and fixes

- Read the transcript back to the member before cutting; names are the usual errors.
- Put corrections in `plan.json → fixes` (display only, timing is untouched).
- Numbers may come as words or digits — decide per video and fix in `fixes` for consistency.
- Noisy audio hurts every engine. If the audio is bad, say so early; a lapel mic next time.

## 7. Privacy

Local = the audio never leaves the computer. Cloud engines receive the audio (the studio sends
a compressed voice-only file and, for Soniox, deletes it from their server after use). For
client material under NDA, prefer local.
