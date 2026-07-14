import argparse
import csv
import json
import re
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "test-results"

# words treated as identical during comparison (semantic match, full score);
# extend as gold-vs-output diffs surface variants that don't actually matter
ALIASES = {
    "sprawny": "sprawna",
    "sprawne": "sprawna",
}
#this needs to be smarter
NUMBER_WORDS = {
    "zero": 0, "jeden": 1, "jedna": 1, "jedno": 1, "dwa": 2, "dwie": 2, "trzy": 3,
    "cztery": 4, "pięć": 5, "sześć": 6, "siedem": 7, "osiem": 8, "dziewięć": 9,
    "dziesięć": 10, "jedenaście": 11, "dwanaście": 12,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


#file parsing

def parse_entries(path: str | Path) -> list[tuple[str, str]]:
    """Parse a prompt-then-JSON file into (prompt, raw_json_str) pairs."""
    entries: list[tuple[str, str]] = []
    prompt: str | None = None
    buf: list[str] = []
    depth = 0

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if depth == 0 and not buf:
            if not stripped:
                continue
            if not stripped.startswith("{"):
                prompt = _unquote(stripped)
                continue
        buf.append(line)
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            entries.append((prompt or "", "\n".join(buf).strip()))
            prompt, buf, depth = None, [], 0
    return entries


def _unquote(line: str) -> str:
    if line.startswith('"') and line.endswith('"') and len(line) >= 2:
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return line[1:-1]
    return line


def normalize_prompt(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt).strip().lower()


#value normalization, no reason to punish for formatting differences especially with SLM

def norm_light(text: str) -> str:
    """Case, punctuation, and whitespace-insensitive form.

    Keeps '.' and ',' when they sit between digits (decimal separators).
    """
    text = text.lower()
    text = re.sub(r"(?<!\d)[.,]|[.,](?!\d)|[;:!?\"'()\[\]_-]", " ", text)
    return " ".join(ALIASES.get(w, w) for w in text.split())


def norm_heavy(text: str) -> str:
    """norm_light + spelled-out numbers converted to digits."""
    words = []
    for w in norm_light(text).split():
        words.append(str(NUMBER_WORDS[w]) if w in NUMBER_WORDS else w)
    return " ".join(words)


def to_number(value) -> float | None:
    """Extract a numeric meaning from a value, if any ('3 kg' -> 3, '2,5 bara' -> 2.5)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = norm_heavy(value).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)(?:\s+i\s+pół)?", text)
    if not m:
        return None
    num = float(m.group(1))
    if "i pół" in text[m.start():]:
        num += 0.5
    return num


#scoring 

def score_scalar(gold, output) -> tuple[str, float, str]:
    """Return (category, score, note) for one non-list field."""
    if gold is None and output is None:
        return "exact", 1.0, ""
    if gold is None:
        return "hallucination", 0.0, "gold is null, model invented a value"
    if output is None:
        return "missing", 0.25, "gold has a value, model gave null"

    if type(gold) is type(output) and gold == output:
        return "exact", 1.0, ""

    if isinstance(gold, str) and isinstance(output, str):
        if norm_light(gold) == norm_light(output):
            return "semantic", 1.0, "semantically identical, formatting differs"
        if norm_heavy(gold) == norm_heavy(output):
            return "format", 0.75, "matches after number-word normalization"

    gold_num, out_num = to_number(gold), to_number(output)
    if gold_num is not None and out_num is not None and gold_num == out_num:
        return "format", 0.75, "same numeric value, type/format differs"

    return "wrong", 0.0, "value does not match gold"


def score_list(gold: list, output) -> tuple[str, float, str]:
    """Score a list field (e.g. defects) by best-matching items."""
    if output is None:
        if not gold:
            return "format", 0.75, "null instead of empty list"
        return "missing", 0.25, "gold has items, model gave null"
    if not isinstance(output, list):
        return "wrong", 0.0, f"expected a list, got {type(output).__name__}"
    if not gold and not output:
        return "exact", 1.0, ""

    remaining = list(output)
    item_scores, notes = [], []
    for gold_item in gold:
        best = ("missing", 0.25, "no matching item in output")
        best_idx = None
        for i, out_item in enumerate(remaining):
            cand = score_scalar(gold_item, out_item)
            if cand[1] > best[1]:
                best, best_idx = cand, i
        if best_idx is not None:
            remaining.pop(best_idx)
        item_scores.append(best[1])
        if best[1] < 1.0:
            notes.append(f"{gold_item!r}: {best[0]}")
    for extra in remaining:
        item_scores.append(0.0)
        notes.append(f"extra item {extra!r}: hallucination")

    denom = max(len(gold), len(output), 1)
    score = sum(item_scores) / denom
    if score == 1.0:
        return "exact", 1.0, ""
    return "partial", round(score, 2), "; ".join(notes)


def score_entry(gold_obj: dict, model_obj: dict) -> tuple[list[dict], float, str, str]:
    """Score all fields of one prompt. Returns (field_rows, entry_score, status, note)."""
    rows = []
    for key, gold_val in gold_obj.items():
        out_val = model_obj.get(key) if key in model_obj else None
        if key not in model_obj:
            category, score, note = "missing", 0.25, "key absent from model output"
        elif isinstance(gold_val, list):
            category, score, note = score_list(gold_val, out_val)
        else:
            category, score, note = score_scalar(gold_val, out_val)
        rows.append({"field": key, "gold": gold_val, "output": out_val,
                     "category": category, "score": score, "note": note})

    for key in model_obj:
        if key not in gold_obj:
            rows.append({"field": key, "gold": None, "output": model_obj[key],
                         "category": "hallucination", "score": 0.0,
                         "note": "key not in gold (invented)"})

    entry_score = round(sum(r["score"] for r in rows) / len(rows), 3) if rows else 0.0

    # null-flood rule: gold fully populated but model mostly null -> FAIL
    status, note = "OK", ""
    gold_keys = list(gold_obj.keys())
    if gold_keys and all(gold_obj[k] is not None for k in gold_keys):
        nulls = sum(1 for k in gold_keys if model_obj.get(k) is None)
        if nulls / len(gold_keys) > 0.5:
            status = "FAIL"
            note = f"null_flood: {nulls}/{len(gold_keys)} fields null while gold has all fields"
    return rows, entry_score, status, note


# reporting 

def write_results(path: Path, all_rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["prompt_id", "prompt", "field", "category", "score", "gold", "output", "note"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in all_rows:
            row = dict(row)
            row["gold"] = json.dumps(row["gold"], ensure_ascii=False)
            row["output"] = json.dumps(row["output"], ensure_ascii=False)
            writer.writerow(row)


def _cell(value) -> str:
    """Render a value for a markdown table cell."""
    if value is None:
        return "—"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text.replace("|", "\\|").replace("\n", " ")


def write_markdown(path: Path, all_rows: list[dict]) -> None:
    """Human-readable report: summary table + one field table per prompt."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # group rows per prompt, split off the _entry summary row
    entries: dict[int, dict] = {}
    for row in all_rows:
        entry = entries.setdefault(row["prompt_id"], {"prompt": row["prompt"], "fields": [], "meta": None})
        (entry.__setitem__("meta", row) if row["field"] == "_entry" else entry["fields"].append(row))

    scores = [0.0 if e["meta"]["category"] != "OK" else e["meta"]["score"] for e in entries.values()]
    failed = sum(1 for e in entries.values() if e["meta"]["category"] != "OK")

    lines = ["# Test results", ""]
    if scores:
        lines.append(f"**Prompts:** {len(scores)} · **Failed:** {failed} · "
                     f"**Avg score:** {sum(scores) / len(scores):.2f}")
    lines += ["", "| # | Prompt | Result | Score |", "|---|--------|--------|-------|"]
    for pid, e in entries.items():
        meta = e["meta"]
        icon = "✅" if meta["category"] == "OK" and meta["score"] == 1.0 else \
               "⚠️" if meta["category"] == "OK" else "❌"
        lines.append(f"| {pid} | {_cell(e['prompt'])} | {icon} {meta['category']} | {meta['score']:.2f} |")

    for pid, e in entries.items():
        meta = e["meta"]
        lines += ["", f"## [{pid}] {e['prompt']}", ""]
        if meta["category"] in ("NO_OUTPUT", "BAD_JSON"):
            lines.append(f"**{meta['category']}** — "
                         + ("the model never answered this prompt." if meta["category"] == "NO_OUTPUT"
                            else f"the model's answer was not valid JSON: `{_cell(meta['note'])}`"))
            continue
        lines.append(f"Entry score: **{meta['score']:.2f}**"
                     + (f" — **FAILED** ({meta['note']})" if meta["category"] == "FAIL" else ""))
        lines += ["", "| Field | Verdict | Score | Gold | Model output | Note |",
                  "|-------|---------|-------|------|--------------|------|"]
        for r in e["fields"]:
            mark = "✓" if r["score"] == 1.0 else "✗"
            lines.append(f"| {r['field']} | {mark} {r['category']} | {r['score']:.2f} "
                         f"| {_cell(r['gold'])} | {_cell(r['output'])} | {_cell(r['note']) if r['note'] else ''} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Score model output against a gold file.")
    parser.add_argument("output_file", help="model output file (from harness.py)")
    parser.add_argument("gold_file", help="gold file (.md/.txt/.json, prompt-then-JSON structure)")
    parser.add_argument("--results", default=None, help="path for the results CSV")
    args = parser.parse_args()

    gold_entries = parse_entries(args.gold_file)
    model_entries = {normalize_prompt(p): raw for p, raw in parse_entries(args.output_file)}

    results_path = Path(args.results) if args.results \
        else RESULTS_DIR / f"{Path(args.output_file).stem}_results.csv"

    all_rows: list[dict] = []
    entry_scores: list[float] = []
    failed = 0

    for idx, (prompt, gold_raw) in enumerate(gold_entries, 1):
        print(f'\n=== [{idx}] "{prompt}"')
        try:
            gold_obj = json.loads(gold_raw)
        except json.JSONDecodeError as e:
            print(f"  [gold file has invalid JSON here: {e}]")
            continue

        base = {"prompt_id": idx, "prompt": prompt}
        model_raw = model_entries.get(normalize_prompt(prompt))

        if model_raw is None:
            failed += 1
            entry_scores.append(0.0)
            print("  NO_OUTPUT — prompt not found in model output file")
            all_rows.append({**base, "field": "_entry", "category": "NO_OUTPUT",
                             "score": 0.0, "gold": None, "output": None, "note": ""})
            continue

        try:
            model_obj = json.loads(model_raw)
        except json.JSONDecodeError as e:
            failed += 1
            entry_scores.append(0.0)
            print(f"  BAD_JSON — model output is not valid JSON ({e})")
            all_rows.append({**base, "field": "_entry", "category": "BAD_JSON",
                             "score": 0.0, "gold": None, "output": model_raw, "note": str(e)})
            continue

        rows, entry_score, status, note = score_entry(gold_obj, model_obj)
        if status == "FAIL":
            failed += 1
        entry_scores.append(0.0 if status == "FAIL" else entry_score)

        for r in rows:
            all_rows.append({**base, **r})
            mark = "✓" if r["score"] == 1.0 else "✗"
            detail = f" — {r['note']}" if r["note"] else ""
            if r["score"] == 1.0 and r["category"] == "exact":
                print(f"  ✓ {r['field']}")
            else:
                print(f"  {mark} {r['field']} [{r['category']} {r['score']:.2f}] "
                      f"gold={r['gold']!r} output={r['output']!r}{detail}")

        all_rows.append({**base, "field": "_entry", "category": status,
                         "score": entry_score, "gold": None, "output": None, "note": note})
        flag = f"  ** {status}: {note}" if status == "FAIL" else ""
        print(f"  entry score: {entry_score:.2f}{flag}")

    write_results(results_path, all_rows)
    report_path = results_path.with_suffix(".md")
    write_markdown(report_path, all_rows)

    print("\n--- summary ---")
    print(f"prompts:      {len(entry_scores)}  ({failed} failed)")
    if entry_scores:
        print(f"avg score:    {sum(entry_scores) / len(entry_scores):.2f}")
    print(f"results csv:  {results_path}")
    print(f"report:       {report_path}")


if __name__ == "__main__":
    main()
