"""Check Git submission candidates without printing private values."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FORBIDDEN_PATHS = {".env", "config/challenge.json"}


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    candidates = [Path(path.decode("utf-8")) for path in result.stdout.split(b"\0") if path]
    violations: list[str] = []
    for path in candidates:
        if path.as_posix() in FORBIDDEN_PATHS:
            violations.append(f"Forbidden path: {path.as_posix()}")

    env = dotenv_values(ROOT / ".env")
    secrets = [env.get(name) for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")]
    secrets = [value.encode("utf-8") for value in secrets if value and len(value) >= 8]

    challenge_messages: list[bytes] = []
    challenge_path = ROOT / "config" / "challenge.json"
    challenge_available = challenge_path.exists()
    if challenge_available:
        from app.challenge import load_challenge

        challenge_messages = [
            query["message"].encode("utf-8") for query in load_challenge(challenge_path).queries
        ]

    checked = 0
    for path in candidates:
        absolute = ROOT / path
        if not absolute.is_file():
            continue
        data = absolute.read_bytes()
        checked += 1
        if any(secret in data for secret in secrets):
            violations.append(f"Langfuse key found: {path.as_posix()}")
        if any(message in data for message in challenge_messages):
            violations.append(f"Private challenge query found: {path.as_posix()}")

    print(f"Git candidates scanned: {checked}")
    print(f"Forbidden path matches: {sum(item.startswith('Forbidden path') for item in violations)}")
    print(f"Langfuse key matches: {sum(item.startswith('Langfuse key') for item in violations)}")
    if challenge_available:
        print(f"Private challenge query matches: {sum(item.startswith('Private challenge') for item in violations)}")
    else:
        print("Private challenge query scan: SKIPPED (config/challenge.json unavailable)")
    if violations:
        print("Affected paths:")
        for item in violations:
            print(f"  {item}")
        return 1
    print("Submission scan: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
