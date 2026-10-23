#!/usr/bin/env python3
"""Copy the shared platform baseline into each audit skill.

Skills can be installed one at a time (npx skills, manual zip), so each skill
carries its own copy of the baseline in references/platform-baseline.md.
Edit shared/os11-platform-baseline.md, then run this script.

Usage:
    python3 scripts/sync_baseline.py           # write the copies
    python3 scripts/sync_baseline.py --check   # exit 1 if any copy is stale
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "shared" / "os11-platform-baseline.md"
SKILLS = [
    "os11-audit-architecture",
    "os11-audit-security",
    "os11-audit-performance",
    "os11-audit-maintainability",
]


def main() -> int:
    check = "--check" in sys.argv[1:]
    expected = SOURCE.read_bytes()
    stale = []
    for skill in SKILLS:
        target = ROOT / "skills" / skill / "references" / "platform-baseline.md"
        if target.exists() and target.read_bytes() == expected:
            continue
        if check:
            stale.append(target.relative_to(ROOT))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected)
        print(f"updated {target.relative_to(ROOT)}")
    if stale:
        for path in stale:
            print(f"error: {path} is out of date; run python3 scripts/sync_baseline.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
