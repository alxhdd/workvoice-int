import argparse
import json
import os
import re
import select
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import requests

# defaults; override with flags or HARNESS_API_URL / HARNESS_MODEL env vars
# llama.cpp server (llama-server) serves one model on port 8080; the model name
# here is only used for labeling the output file.
API_URL = os.environ.get("HARNESS_API_URL", "http://localhost:8080/v1/chat/completions")
# system_prompt.txt next to this script is used automatically if it exists;
# pass --system-prompt-file to use another one (or --no-system-prompt for none)
SYS_PROMPT_FILE = Path(__file__).resolve().parent / "system_prompt.txt"
MODEL = os.environ.get("HARNESS_MODEL", "gemma-4-e2b-q4")
MAX_TOKENS = 512  # extraction outputs are small; caps generation time on CPU, can be adjusted 

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "model-output"


def assemble_prompt(user_prompt: str, system_prompt: str | None) -> list[dict]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    return messages


def query_model(api_url: str, model: str, messages: list[dict], timeout: float) -> str:
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS,
        # llama.cpp extension: never reuse KV cache between requests — every
        # prompt gets a completely fresh context (context isolation is critical here, run into some minor leaks originally)
        "cache_prompt": False,
    }
    response = requests.post(api_url, json=body, timeout=timeout)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def check_server(api_url: str) -> None:
    """Fail fast with a useful message if the container isn't reachable."""
    parts = urlsplit(api_url)
    base = f"{parts.scheme}://{parts.netloc}"
    try:
        requests.get(base, timeout=3)
    except requests.ConnectionError:
        raise SystemExit(
            f"Can't reach {base} — is the model container running?\n"
            "Check with `docker ps` and that the port is published (-p host:container)."
        )
    except requests.RequestException:
        pass  # reachable but grumpy about GET / — that's fine, POST will work


def output_path(model: str) -> Path:
    safe_model = re.sub(r"[^A-Za-z0-9._-]", "-", model)
    return OUTPUT_DIR / f"{date.today().isoformat()}_{safe_model}.md"

#cleanup
def clean_json_output(text: str) -> str:
    """Unwrap ```json fences if the model added them; otherwise return as-is."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return m.group(1).strip() if m else text

#parsi g output for easy tests
def save_record(path: Path, prompt: str, output: str) -> None:
    """Append one entry matching the gold-file structure:

    "the prompt"
    {json output}
    """
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(prompt, ensure_ascii=False) + "\n")
        f.write(clean_json_output(output) + "\n\n")

#actual call happens here
def run_prompt(args, system_prompt: str | None, path: Path, user_prompt: str) -> str | None:
    """Query the model with one prompt; save and return the output (None on error)."""
    messages = assemble_prompt(user_prompt, system_prompt)
    try:
        output = query_model(args.api_url, args.model, messages, args.timeout)
    except requests.RequestException as e:
        print(f"[error] request failed: {e}")
        return None
    save_record(path, user_prompt, output)
    return output


def read_prompt() -> str:
    """Read one prompt; if a multi-line block was pasted, merge it into one prompt.
    input() only returns the first line of a paste — the rest would silently
    become the *next* prompts, splitting one dictation across requests. On a
    real terminal, any lines already buffered right after Enter are part of
    the same paste, so drain and join them.
    """
    lines = [input("> ")]
    if sys.stdin.isatty():
        while select.select([sys.stdin], [], [], 0.05)[0]:
            line = sys.stdin.readline()
            if not line:
                break
            lines.append(line)
    return " ".join(part.strip() for part in lines if part.strip())


def run_interactive(args, system_prompt: str | None, path: Path) -> None:
    while True:
        try:
            user_prompt = read_prompt()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_prompt:
            continue
        if user_prompt.lower() in ["exit", "quit", "q"]:
            break
        print("[waiting for model...]", flush=True)
        output = run_prompt(args, system_prompt, path, user_prompt)
        if output is not None:
            print(output)

#batching from file
def run_batch(args, system_prompt: str | None, path: Path, prompts_file: str) -> None:
    prompts = [
        line.strip()
        for line in Path(prompts_file).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not prompts:
        raise SystemExit(f"No prompts found in {prompts_file}")

    print(f"Running {len(prompts)} prompts from {prompts_file}")
    failed = 0
    for i, user_prompt in enumerate(prompts, 1):
        preview = user_prompt if len(user_prompt) <= 60 else user_prompt[:57] + "..."
        print(f"[{i}/{len(prompts)}] {preview}")
        if run_prompt(args, system_prompt, path, user_prompt) is None:
            failed += 1
    print(f"Done: {len(prompts) - failed}/{len(prompts)} succeeded, saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="Prompt a model and log prompt/output pairs.")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--api-url", default=API_URL)
    parser.add_argument("--system-prompt-file", default=SYS_PROMPT_FILE)
    parser.add_argument("--no-system-prompt", action="store_true",
                        help="send prompts raw, without any system prompt")
    parser.add_argument("--prompts-file", default=None,
                        help="run in batch mode over this file (one prompt per line), skipping the menu")
    parser.add_argument("--timeout", type=float, default=120,
                        help="seconds to wait for a response (first request after container start can be slow)")
    args = parser.parse_args()

    system_prompt = None
    if not args.no_system_prompt and args.system_prompt_file and Path(args.system_prompt_file).is_file():
        system_prompt = Path(args.system_prompt_file).read_text(encoding="utf-8").strip()
        print(f"System prompt: {args.system_prompt_file}")

    check_server(args.api_url)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = output_path(args.model)
    print(f"Model: {args.model} @ {args.api_url}")
    print(f"Logging to {path}")

    if args.prompts_file:
        run_batch(args, system_prompt, path, args.prompts_file)
        return

    while True:
        mode = input("Mode — [1] interactive, [2] batch from prompts file: ").strip()
        if mode == "1":
            run_interactive(args, system_prompt, path)
            return
        if mode == "2":
            prompts_file = input("Path to prompts file: ").strip()
            if not Path(prompts_file).is_file():
                print(f"No such file: {prompts_file}")
                continue
            run_batch(args, system_prompt, path, prompts_file)
            return
        print("Type 1 or 2.")


if __name__ == "__main__":
    main()
