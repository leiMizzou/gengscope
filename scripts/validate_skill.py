#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: validate_skill.py <skill-dir>", file=sys.stderr)
        return 2
    skill_dir = Path(args[0])
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        print(f"missing {skill_file}", file=sys.stderr)
        return 1
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        print("SKILL.md must start with YAML frontmatter", file=sys.stderr)
        return 1
    fields = _frontmatter_fields(match.group("frontmatter"))
    name = fields.get("name", "")
    description = fields.get("description", "")
    if not re.fullmatch(r"[a-z0-9-]{1,63}", name):
        print(f"invalid skill name: {name!r}", file=sys.stderr)
        return 1
    if name != skill_dir.name:
        print(f"skill folder must match frontmatter name: {skill_dir.name!r} != {name!r}", file=sys.stderr)
        return 1
    if len(description) < 80 or "Use when" not in description:
        print("description must be a substantial trigger description containing 'Use when'", file=sys.stderr)
        return 1
    openai_yaml = skill_dir / "agents" / "openai.yaml"
    if not openai_yaml.exists():
        print("missing agents/openai.yaml", file=sys.stderr)
        return 1
    openai_text = openai_yaml.read_text(encoding="utf-8")
    if f"Use ${name}" not in openai_text:
        print("agents/openai.yaml default_prompt must mention the skill as $skill-name", file=sys.stderr)
        return 1
    return 0


def _frontmatter_fields(frontmatter: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    for line in frontmatter.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            fields[current_key] = value.strip().strip('"')
        elif current_key:
            fields[current_key] += " " + line.strip().strip('"')
    return fields


if __name__ == "__main__":
    raise SystemExit(main())
