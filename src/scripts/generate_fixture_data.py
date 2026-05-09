"""Generate fixture seed and expected outputs from Markdown definitions."""

from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil


def parse_frontmatter(markdown_text: str, source_path: str) -> dict[str, object]:
    lines = markdown_text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise ValueError(f"Missing frontmatter in {source_path}")

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError(f"Unterminated frontmatter in {source_path}")

    meta: dict[str, object] = {}
    key: str | None = None
    for raw_line in lines[1:end_idx]:
        line = raw_line.rstrip()
        if not line:
            continue

        stripped = line.strip()
        if stripped.startswith("- "):
            if key is None:
                raise ValueError(f"List entry without key in frontmatter: {source_path}")
            value = stripped[2:].strip()
            current = meta.get(key, [])
            if not isinstance(current, list):
                raise ValueError(f"Mixed scalar/list values for key '{key}' in {source_path}")
            current.append(value)
            meta[key] = current
            continue

        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line in {source_path}: {line}")
        split_idx = line.index(":")
        key = line[:split_idx].strip()
        value = line[split_idx + 1 :].strip()
        if value:
            meta[key] = value
        else:
            meta[key] = []

    body = "\n".join(lines[end_idx + 1 :]).strip() + "\n"
    meta["body"] = body
    return meta


def read_markdown_definitions(definitions_root: Path) -> list[dict[str, object]]:
    if not definitions_root.exists():
        raise ValueError("fixtures/definitions does not exist")

    note_files = sorted(
        path
        for path in definitions_root.rglob("*.md")
        if path.name.lower() != "readme.md" and not any(part.startswith(".") for part in path.parts)
    )
    if not note_files:
        raise ValueError(
            "No fixture note definitions found. Add Markdown note files under fixtures/definitions/"
        )

    notes: list[dict[str, object]] = []
    for note_file in note_files:
        rel = note_file.relative_to(definitions_root)
        notebook_path = "/".join(rel.parts[:-1])
        source_path = f"fixtures/definitions/{rel.as_posix()}"
        parsed = parse_frontmatter(note_file.read_text(encoding="utf-8"), source_path)

        required = ["slug", "title", "created", "updated"]
        missing = [field for field in required if not parsed.get(field)]
        if missing:
            raise ValueError(f"Missing required frontmatter fields {missing} in {source_path}")

        tags = parsed.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            raise ValueError(f"Invalid tags format in {source_path}")

        slug = str(parsed["slug"])
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"Invalid slug '{slug}' in {source_path}")

        note_key = f"{notebook_path}/{slug}" if notebook_path else slug
        note_id = hashlib.sha256(note_key.encode("utf-8")).hexdigest()[:24]
        notebook_id = hashlib.sha256(notebook_path.encode("utf-8")).hexdigest()[:24]

        notes.append(
            {
                "source_path": source_path,
                "notebook_path": notebook_path,
                "notebook_id": notebook_id,
                "slug": slug,
                "note_id": note_id,
                "title": str(parsed["title"]),
                "created": str(parsed["created"]),
                "updated": str(parsed["updated"]),
                "tags": sorted(str(tag) for tag in tags),
                "body": str(parsed["body"]),
            }
        )

    notes.sort(key=lambda item: (item["notebook_path"], item["slug"]))
    return notes


def sql_escape(value: str) -> str:
    return value.replace("'", "''")


def render_seed_sql(notes: list[dict[str, object]]) -> str:
    notebook_paths = sorted({str(note["notebook_path"]) for note in notes})
    notebook_rows: list[str] = []
    for notebook_path in notebook_paths:
        notebook_id = hashlib.sha256(notebook_path.encode("utf-8")).hexdigest()[:24]
        notebook_rows.append(
            "(" + ", ".join([
                f"'{sql_escape(notebook_id)}'",
                f"'{sql_escape(notebook_path)}'",
            ]) + ")"
        )

    note_rows: list[str] = []
    for note in notes:
        note_rows.append(
            "(" + ", ".join([
                f"'{sql_escape(str(note['note_id']))}'",
                f"'{sql_escape(str(note['notebook_id']))}'",
                f"'{sql_escape(str(note['slug']))}'",
                f"'{sql_escape(str(note['title']))}'",
                f"'{sql_escape(str(note['created']))}'",
                f"'{sql_escape(str(note['updated']))}'",
                f"'{sql_escape(str(note['body']))}'",
            ]) + ")"
        )

    sql_parts = [
        "-- Generated by dagger fixture-data stage (default mode)",
        "CREATE TABLE IF NOT EXISTS fixture_seed_notebooks (",
        "  id TEXT PRIMARY KEY,",
        "  path TEXT NOT NULL",
        ");",
        "",
        "CREATE TABLE IF NOT EXISTS fixture_seed_notes (",
        "  id TEXT PRIMARY KEY,",
        "  notebook_id TEXT NOT NULL,",
        "  slug TEXT NOT NULL,",
        "  title TEXT NOT NULL,",
        "  created_at TEXT NOT NULL,",
        "  updated_at TEXT NOT NULL,",
        "  body_md TEXT NOT NULL",
        ");",
        "",
    ]
    if notebook_rows:
        sql_parts.extend(
            [
                "INSERT INTO fixture_seed_notebooks (id, path) VALUES",
                ",\n".join(notebook_rows) + ";",
                "",
            ]
        )
    if note_rows:
        sql_parts.extend(
            [
                (
                    "INSERT INTO fixture_seed_notes "
                    "(id, notebook_id, slug, title, created_at, updated_at, body_md) VALUES"
                ),
                ",\n".join(note_rows) + ";",
                "",
            ]
        )

    return "\n".join(sql_parts) + "\n"


def render_expected_json(notes: list[dict[str, object]]) -> str:
    payload = {
        "generated_from": "fixtures/definitions",
        "notes": [
            {
                "id": note["note_id"],
                "notebook_path": note["notebook_path"],
                "slug": note["slug"],
                "title": note["title"],
                "created": note["created"],
                "updated": note["updated"],
                "tags": note["tags"],
            }
            for note in notes
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def parse_lock_file(lock_path: Path) -> dict[str, str]:
    if not lock_path.exists():
        return {}

    checksums: dict[str, str] = {}
    for raw_line in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        checksum, rel_path = parts
        checksums[rel_path] = checksum
    return checksums


def compute_generated_checksums(files: dict[str, str]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for rel_path in sorted(files):
        digest = hashlib.sha256(files[rel_path].encode("utf-8")).hexdigest()
        checksums[f"fixtures/{rel_path}"] = digest
    return checksums


def render_lock_file(checksums: dict[str, str]) -> str:
    lines = [
        "# Fixture Lock",
        "#",
        "# This file is the authoritative checksum manifest for all fixture data.",
        "# It is generated by `dagger call fixture-data` and must be committed.",
        "#",
        "# To regenerate: dagger call fixture-data --update-lock",
        "# CI will fail if this file does not match the current fixture data.",
        "#",
        "# Format:",
        "#   <sha256-hex>  fixtures/<path-relative-to-fixtures-root>",
        "#",
        "# DO NOT edit this file manually.",
        "",
    ]
    for rel_path in sorted(checksums):
        lines.append(f"{checksums[rel_path]}  {rel_path}")
    lines.append("")
    return "\n".join(lines)


def render_definition_report(notes: list[dict[str, object]], actual: dict[str, str], locked: dict[str, str]) -> str:
    lines = [
        "# Fixture Definitions Review",
        "",
        "This report centers the canonical Markdown fixture definitions that drive generated fixture outputs.",
        "",
        "## Definition Inventory",
        "",
    ]

    if notes:
        for note in notes:
            tags = ", ".join(note["tags"]) if note["tags"] else "(none)"
            lines.append(
                f"- `{note['source_path']}` | notebook: `{note['notebook_path']}` | slug: `{note['slug']}` | title: `{note['title']}` | tags: `{tags}`"
            )
    else:
        lines.append("- No fixture definitions found.")

    lines.extend([
        "",
        "## Output Validation",
        "",
    ])

    added = sorted(set(actual) - set(locked))
    removed = sorted(set(locked) - set(actual))
    changed = sorted(key for key in actual if key in locked and actual[key] != locked[key])

    if not added and not removed and not changed:
        lines.append("- Generated output checksums match the committed baseline.")
    else:
        lines.append("- Generated output checksum changes detected from the current definition set:")
        if added:
            for rel_path in added:
                lines.append(f"  - Added `{rel_path}`")
        if removed:
            for rel_path in removed:
                lines.append(f"  - Removed `{rel_path}`")
        if changed:
            for rel_path in changed:
                lines.append(f"  - Changed `{rel_path}`")

    lines.extend([
        "",
        "## Generated Checksums",
        "",
    ])

    if actual:
        for rel_path in sorted(actual):
            lines.append(f"- `{rel_path}`: `{actual[rel_path]}`")
    else:
        lines.append("- No generated outputs found.")

    lines.append("")
    return "\n".join(lines)


def raise_lock_divergence(actual: dict[str, str], locked: dict[str, str]) -> None:
    added = sorted(set(actual) - set(locked))
    removed = sorted(set(locked) - set(actual))
    changed = sorted(key for key in actual if key in locked and actual[key] != locked[key])

    details: list[str] = []
    if added:
        details.append(f"Added: {added}")
    if removed:
        details.append(f"Removed: {removed}")
    if changed:
        details.append(f"Changed: {changed}")

    raise ValueError(
        "fixture.lock divergence detected for generated outputs (seed/ + expected/). "
        "Run `dagger call fixture-data --update-lock` to regenerate lock artifacts.\n"
        + "\n".join(details)
    )


def copy_tree(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    shutil.copytree(src, dest, dirs_exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures-root", required=True)
    parser.add_argument("--output-fixtures-root", required=True)
    parser.add_argument("--update-lock", default="false")
    return parser.parse_args()


def to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> None:
    args = parse_args()
    fixtures_root = Path(args.fixtures_root)
    output_fixtures_root = Path(args.output_fixtures_root)

    definitions_root = fixtures_root / "definitions"
    lock_path = fixtures_root / "fixture.lock"

    locked = parse_lock_file(lock_path)
    if not to_bool(args.update_lock) and (not lock_path.exists() or not locked):
        raise ValueError(
            "fixture.lock is missing or empty for default mode. "
            "Run `dagger call fixture-data --update-lock` to generate lock artifacts first."
        )

    notes = read_markdown_definitions(definitions_root)
    generated_files = {
        "seed/seed.sql": render_seed_sql(notes),
        "expected/notes.json": render_expected_json(notes),
    }

    actual = compute_generated_checksums(generated_files)
    if not to_bool(args.update_lock) and actual != locked:
        raise_lock_divergence(actual, locked)

    copy_tree(definitions_root, output_fixtures_root / "definitions")
    (output_fixtures_root / "seed").mkdir(parents=True, exist_ok=True)
    (output_fixtures_root / "expected").mkdir(parents=True, exist_ok=True)

    if to_bool(args.update_lock):
        (output_fixtures_root / "fixture.lock").write_text(
            render_lock_file(actual),
            encoding="utf-8",
        )
        (output_fixtures_root / "fixture-diff.md").write_text(
            render_definition_report(notes, actual, locked),
            encoding="utf-8",
        )
    else:
        (output_fixtures_root / "fixture.lock").write_text(
            lock_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    (output_fixtures_root / "seed" / "seed.sql").write_text(
        generated_files["seed/seed.sql"],
        encoding="utf-8",
    )
    (output_fixtures_root / "expected" / "notes.json").write_text(
        generated_files["expected/notes.json"],
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
