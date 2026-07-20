# interceptor_seeker — video demo guide (SYNTHETIC)

One-command live demonstration for screen recording. Terminal-based live
view (channel Trust Coefficients as bars + diagnosis + engagement-confidence
level). All data is synthetic and labeled on screen.

## Run commands

```sh
# interactive (recommended for the video): ENTER injects, ENTER clears
python tools/video_demo.py                     # ir_decoy
python tools/video_demo.py --scenario rf_jam   # second take

# scripted timed injection (no keypress; for CI / piped terminals)
python tools/video_demo.py --auto --inject-after 5 --clear-after 5
python tools/video_demo.py --auto --scenario rf_jam

# slow it down / speed it up for the recording
python tools/video_demo.py --speed 0.5         # half real-time
```

Interactive mode requires a real terminal (TTY). If stdin is piped it falls
back to `--auto` automatically.

## What appears on screen, by phase

1. **CLEAN (t ≈ 0–warmup, then until inject):** three bars near full
   (`OK`, ≥0.85). Diagnosis `nominal`. Confidence `NORMAL`. Footer prompts
   "PRESS ENTER TO INJECT" (or an auto-inject countdown).
2. **INJECT (you press ENTER):** footer flips to ">>> FAULT ACTIVE". Within
   ~0.3–0.5 s the faulted channel's bar drops through `LOW` (0.55) to `!!!`,
   a `>>> ENGAGEMENT-CONFIDENCE: NORMAL -> CAUTION -> CRITICAL` banner prints
   (with a terminal bell), and the diagnosis line names the fault
   (`ir_decoy` or `rf_jam`) at a rising %.
   - ir_decoy: **ir_seeker** collapses (~0.46 min); rf/ins stay up-ish.
   - rf_jam: **rf_seeker** collapses (~0.07 min); ir sags via the shared
     bearing edge (documented coupling), ins stays high.
3. **CLEAR (you press ENTER again):** footer "FAULT CLEARED"; the faulted
   channel's bar climbs back and confidence de-escalates
   (`CRITICAL -> NORMAL` for ir_decoy).

## Suggested narration timing (interactive, ~real time)

| time | say |
|---|---|
| 0:00 | "A closing intercept. Three seeker channels — IR, RF, INS — each with a live Trust Coefficient." |
| 0:03 | "All green: the physical cross-checks between channels agree." |
| ~0:06 (press ENTER) | "Now I inject an IR decoy — bearing pulled off the true target." |
| +0.5 s | "Under half a second, IR trust collapses; the diagnosis names the decoy, not RF or INS." |
| ~ | "Engagement confidence drops to CRITICAL — the fire-control advisory to hold terminal commit and hand over to the trusted channel." |
| press ENTER | "Decoy removed — trust recovers, confidence returns to NORMAL, no latching." |

Record the terminal at a font size where the bars and the `>>>` banners are
legible. `--speed 0.5` gives more time to narrate.
