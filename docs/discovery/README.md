# docs/discovery/ — real customer-discovery records

The method lives in `discovery_and_validation.md` (the cold-discovery question set, the A1–A13
assumption decoder, the three traps, the "Marco" onboarding placeholder). **This folder is where
*real* interviews land** and get scored against that method, so that `strategic_context.md`'s open
gates move on evidence instead of on the founder's hope.

## The privacy posture (this repo is PUBLIC — non-negotiable)

A real operator's recorded voice and full verbatim transcript are **never committed**. The split:

- **`_raw/` — gitignored working files.** Raw audio and the full verbatim transcript go here. This is
  your private source of truth with every exact word preserved (the method runs on exact quotes). Git
  ignores `_raw/*` and every audio extension anywhere in the repo (see `.gitignore`); only
  `_raw/.gitkeep` is tracked.
- **`<date>_<pseudonym>.md` — the committed decode.** Pseudonymized operator + restaurant, and only the
  curated quotes you actually cite. **Strip location-fingerprinting details** (the "amphitheater 8
  blocks away" kind of specific that IDs a real place). This is what the public repo sees.

If in doubt, it stays in `_raw/`.

## Files

| File | Committed? | What |
|---|---|---|
| `discovery_and_validation.md` | yes | The method + the fictional Marco onboarding. Read first. |
| `_TEMPLATE_interview.md` | yes | Copy this per interview → `<date>_<pseudonym>.md`. |
| `<date>_<pseudonym>.md` | yes | One decoded interview (pseudonymized, curated quotes). |
| `assumption_scoreboard.md` | yes | Rolling A1–A13 tally across all interviews (built once ≥2 exist). |
| `_raw/…` | **no** | Audio + full verbatim transcripts. Gitignored. |

## Workflow per interview

1. **Transcribe** the recording into `_raw/<date>.md` (see the WhisperX guide you're following;
   diarized + timestamped, so "who said what" is preserved — the decode depends on it).
2. **Copy** `_TEMPLATE_interview.md` → `<date>_<pseudonym>.md`.
3. **Decode**: score A1–A13 on what the operator **volunteered organically**, not what you asked
   (prompted topics score as *no signal* — that discipline is the whole point); diff the Marco
   placeholders; check the three traps; capture the referral.
4. **Commit** the decode only. The raw stays in `_raw/`.

## The one statistical rule

One conversation can **kill** an assumption but essentially cannot **confirm** one — especially a warm
or insider-sourced one (the halo trap). The rolling `assumption_scoreboard.md` exists so `n=1` never
reads as validation. Confirmation is a pattern across interviews, aimed deliberately at strugglers, not
a single enthusiastic yes.
