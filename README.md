# Workvoice — On-device structured extraction from Polish field notes

Task: turn messy, voice-transcribed Polish inspection notes into a fixed-schema JSON record, on a small local model, with an eval harness to measure it. Budget was one hour, so this is deliberately rough in places — cuts and assumptions are written down below.

## How to run

```bash
# model container (llama.cpp server) must be up on :8080
python harness.py --prompts-file notes.txt        # or run it bare for interactive mode
python compare.py <model_output_file> <gold_file> [--results <path.csv>]
```

Output lands in `data/model-output/<date>_<model>.md`; compare writes a CSV plus a human-readable markdown report to `data/test-results/`.

## What's here

- **Track 1 (extraction):** system prompt + extraction rules, tested against a local Gemma container via llama.cpp.
- **Track 2 (eval):** `harness.py` + `compare.py` — field-by-field scoring against gold, CSV output, add a note+gold pair and re-run.
- **Track 3 (robustness):** designed, not implemented — see "What I'd do next".
- **Track 4 (on-device):** writeup below.
- **Track 5 (dataset):** ideas below.

## Extraction rules (what the prompt enforces)

The two provided gold examples are used as guidelines in the prompt, plus explicit rules:

- **No inventing.** If a field isn't explicitly stated in the note, it's `null`. Sticking to facts from the note beats plausible guesses — this is the core correctness problem here.
- **Status:** one of `sprawna | do_naprawy | do_wymiany`. If the note doesn't state a status explicitly, `null` — we don't infer it.
- **Dates:** the current date is a daily variable used at evaluation time. Relative phrases resolve against it: "za rok" = date + 1 year, "dzisiaj" = date, "za tydzień" = date + 7 days, etc. If a date is given numerically, use it; if not stated at all, `null`.
- **Location:** main part = building/room; extra detail (floor, indoor/outdoor) goes as additional info.
- **Defects:** catch-all for anything describing faults or shortcomings that doesn't map to an explicit field. `[]` if none mentioned.

### Gold answers for notes 3–5 (my calls)

```jsonc
// Note 3
{ "device_type": "gaśnica CO2", "location": "kuchnia, zaplecze",
  "pressure_bar": null, "capacity": "5 kg",
  "defects": ["brak plomby", "waga poniżej normy"],
  "status": "do_wymiany", "inspection_date": "2026-07-10", "next_inspection": null }

// Note 4
{ "device_type": "hydrant zewnętrzny", "location": "wjazd",
  "pressure_bar": 7, "capacity": null, "defects": [],
  "status": "sprawny", "inspection_date": null, "next_inspection": "2027-07" }

// Note 5
{ "device_type": "gaśnica", "location": "korytarz, pierwsze piętro",
  "pressure_bar": null, "capacity": null,
  "defects": ["data przeglądu minęła"],
  "status": null, "inspection_date": null, "next_inspection": null }
```

Judgment calls worth flagging: in note 5 the overdue inspection lands in `defects` (it's a fault, but not an explicit status), and `status` stays `null` because "reszta wygląda ok" is not "sprawna" — the technician didn't sign off on it, so neither do we.

## Eval harness

`harness.py` takes input, runs it through the model, saves the output.
`compare.py` scores the saved output against gold, field by field, and writes results to `data/test-results/<output-stem>_results.csv` (one row per field + one `_entry` summary row per prompt; gold/output cells are JSON-encoded for unambiguous parsing).

Scoring per field:

| tier | score | meaning |
|---|---|---|
| `exact` | 1.00 | identical value and type |
| `semantic` | 1.00 | same after case/punctuation/whitespace normalization — full score, but flagged in stdout and CSV so it can be audited |
| `format` | 0.75 | same meaning, wrong type/format (`"3 kg"` vs `3`, `"three kg"` vs `"3 kg"`, `2.5` vs `"2.5"`) — Polish and English number words are handled ("trzy", "pięć", "dwa i pół" → 2.5) |
| `missing` | 0.25 | gold has a value, model returned `null` |
| `wrong` / `hallucination` | 0.00 | invented values, values where gold is null, extra keys not in gold |

The asymmetry is deliberate: **null beats invention, always.** A missing value is recoverable (flag for human review); an invented pressure reading on a compliance record is not.

Entry-level rules:
- **Null-flood fail:** if gold has all fields populated and the model nulls >50% of them, the whole entry is marked `FAIL` (with a note like `null_flood: 4/5 fields null`) and scores 0 in the average regardless of its field scores — otherwise "null everything" games the null-friendly scoring.
- `NO_OUTPUT` / `BAD_JSON` also fail the entry.
- **Lists** (defects) score per-item with the same tiers; extra invented items drag the score down.

## Getting valid JSON out of a small model

JSON adherence on a 1B-class model can genuinely be rough — I tested on Gemma, and the mobile-targeted variant is even smaller. In the container, llama.cpp enforces JSON output (in theory — see below).

If the model won't behave, the fix I'd reach for is **constrained / grammar-based decoding** (GBNF grammars in llama.cpp, or Outlines/XGrammar server-side), which masks invalid tokens at sampling time so the output *cannot* violate the schema. The schema here should be small — most fields are `null | <type>` and there aren't that many of them (probably; I don't have blue-collar domain know-how to say how many field types reality actually needs).

## Track 4 — on-device reality

llama.cpp is written in C++, and with a small grammar enforcing adherence, this should run on a mid-range Android phone. "Should" — I haven't verified this end to end, and this is genuinely experimental territory. What breaks first at small scale is JSON adherence and the null-vs-invention discipline, which is exactly why the grammar constraint and the eval harness exist: the model is a component to be constrained and verified, not trusted.

<!-- TODO: expand with concrete quant choice + rough memory/latency numbers if you have them -->

## Track 5 — where does the data come from

We have 5 examples and a chicken-and-egg problem. Quick ideas, honestly not sure yet how realistic each is:

- **YouTube videos of tradespeople** — the jargon is essential and this is where it lives. Build a dataset from transcriptions, use a strong model to extract/structure the data and prepare it for training.
- **Manuals, technical documents, certificates** — to learn the technical register, especially in Polish. Same jargon argument.
- Then **retrain / distill** into whichever small model we settle on. This should give us *something* — and if it fails, at least we'll know exactly where we stand.

## What I cut and what I'd do next

- **Track 3 (critic/retry):** designed but not built. The obvious shape: a retry that rewrites the system prompt based on the scoring notes — keep the fields that came out correct, override the prompt for the failed ones, run again. Honestly, with an SLM this may not buy much, which is part of why it got cut first.
- **Async in the test harness:** pointless at this input size, worthwhile at larger volumes. Cosmetic, but makes life easier. Not now.
- **Semantics are ambiguous:** some things can be enforced more but it's a question of if and what is actually needed because at this scale it's a tradeoff. 

Next I'd test more, tweak more and look into the track4 stuff alongside track3. I'd love to see how the mobile gemma quants work for this use case (gemma is multimodal which makes it a great fit for this if it can actually run.)

## Known issues

Found while stress-testing `compare.py` against simulated SLM output (sanity check gold-vs-gold scores 1.00; a deliberately flawed output correctly triggered every scoring tier — semantic, format, missing, hallucination, partial lists). Two real gaps surfaced:

- **`null_flood` can never fire on this dataset.** The rule requires gold to have *all* fields populated, but every one of the 5 gold records contains at least one legit null (`pressure_bar` or `capacity`). Nulling 4/8 fields on note 4 scored 0.62 "OK" instead of FAIL. Fix: change the condition to "nulls > 50% of the fields gold actually populated" — one line in `score_entry`. Known, not fixed, out of time.
- **Preamble text breaks the parser silently.** A classic SLM answer like `Sure! Here is the JSON: {...` doesn't start with `{`, so `parse_entries` treats it as a new *prompt*: the real prompt gets `NO_OUTPUT` instead of `BAD_JSON` and the malformed record is dropped without a trace. The entry still fails (score 0 either way), so not urgent — but `clean_json_output` in harness.py only strips code fences, not preambles, so this will happen with real model output. A regex grabbing from the first `{` in `clean_json_output` covers most of it.


## Issues hit

- Had to tweak llama.cpp because context leaked between prompts — harness sends `cache_prompt: false` so every request gets a fresh KV cache (context isolation matters here: one dictation must never bleed into the next).

## How I tested

Spun up a Gemma container, ran the provided prompts (both via text file and manual input) against a simple system prompt, scored with the harness above.