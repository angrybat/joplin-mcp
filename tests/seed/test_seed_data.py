"""Seed validation tests for joplin-service stage."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


def _stable_id(prefix: str, value: str) -> str:
    import hashlib

    return hashlib.sha256(f"{prefix}:{value}".encode("utf-8")).hexdigest()[:32]


def _parse_frontmatter(markdown_text: str, source_path: str) -> dict[str, object]:
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


def _load_fixture_notes(fixtures_root: Path) -> list[dict[str, object]]:
    definitions_root = fixtures_root / "definitions"
    note_files = sorted(
        path
        for path in definitions_root.rglob("*.md")
        if path.name.lower() != "readme.md" and not any(part.startswith(".") for part in path.parts)
    )

    notes: list[dict[str, object]] = []
    for note_file in note_files:
        rel = note_file.relative_to(definitions_root)
        notebook_path = "/".join(rel.parts[:-1])
        source_path = f"fixtures/definitions/{rel.as_posix()}"
        parsed = _parse_frontmatter(note_file.read_text(encoding="utf-8"), source_path)

        slug = str(parsed["slug"])
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"Invalid slug '{slug}' in {source_path}")

        tags = parsed.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            raise ValueError(f"Invalid tags format in {source_path}")

        notes.append(
            {
                "source_path": source_path,
                "notebook_path": notebook_path,
                "slug": slug,
                "title": str(parsed["title"]),
                "body": str(parsed["body"]),
                "created": str(parsed["created"]),
                "updated": str(parsed["updated"]),
                "tags": sorted(str(tag) for tag in tags),
            }
        )

    notes.sort(key=lambda item: (item["notebook_path"], item["slug"]))
    return notes


def _build_expectations(fixtures_root: Path) -> dict[str, list[dict[str, str]]]:
    notes = _load_fixture_notes(fixtures_root)
    notebooks: dict[str, dict[str, str]] = {}
    note_rows: list[dict[str, str]] = []
    tags: dict[str, dict[str, str]] = {}
    note_tags: list[dict[str, str]] = []

    for note in notes:
        notebook_path = str(note["notebook_path"])
        parent_id = ""
        if notebook_path:
            current_path = ""
            for segment in notebook_path.split("/"):
                current_path = f"{current_path}/{segment}".strip("/")
                folder_id = _stable_id("folder", current_path)
                if current_path not in notebooks:
                    notebooks[current_path] = {
                        "id": folder_id,
                        "path": current_path,
                        "title": segment,
                    }
                parent_id = folder_id

        note_key = f"{notebook_path}/{note['slug']}" if notebook_path else str(note["slug"])
        note_id = _stable_id("note", note_key)
        note_rows.append(
            {
                "id": note_id,
                "title": str(note["title"]),
                "slug": str(note["slug"]),
                "notebook_path": notebook_path,
                "parent_id": parent_id,
            }
        )

        for tag_title in note["tags"]:
            tag_id = _stable_id("tag", tag_title)
            if tag_title not in tags:
                tags[tag_title] = {
                    "id": tag_id,
                    "title": tag_title,
                }
            note_tag_id = _stable_id("note-tag", f"{note_id}:{tag_id}")
            note_tags.append(
                {
                    "id": note_tag_id,
                    "note_id": note_id,
                    "tag_id": tag_id,
                }
            )

    return {
        "notebooks": [notebooks[key] for key in sorted(notebooks, key=lambda path: (path.count("/"), path))],
        "notes": note_rows,
        "tags": [tags[key] for key in sorted(tags)],
        "note_tags": sorted(note_tags, key=lambda row: row["id"]),
    }


def _open_request(request: urllib.request.Request) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.getcode(), response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


@pytest.fixture(scope="session")
def joplin_base_url() -> str:
    return os.environ.get("JOPLIN_BASE_URL", "http://joplin:22300")


@pytest.fixture(scope="session")
def session_id(joplin_base_url: str) -> str:
    email = os.environ.get("JOPLIN_ADMIN_EMAIL", "admin@localhost")
    password = os.environ.get("JOPLIN_ADMIN_PASSWORD", "admin")

    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{joplin_base_url}/api/sessions",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    last_status = 0
    last_body = ""
    for _ in range(20):
        status, body = _open_request(request)
        last_status = status
        last_body = body
        if status == 200:
            return str(json.loads(body)["id"])
        time.sleep(1)

    raise RuntimeError(f"Could not create Joplin session: status={last_status}, body={last_body!r}")


@pytest.fixture(scope="session")
def seeded_items() -> dict[str, list[dict[str, str]]]:
    fixtures_root = Path(os.environ.get("FIXTURES_ROOT", "fixtures"))
    return _build_expectations(fixtures_root)


EXPECTED_ITEMS = _build_expectations(Path(os.environ.get("FIXTURES_ROOT", "fixtures")))


def _fetch_item_content(base_url: str, session: str, item_id: str) -> str:
    request = urllib.request.Request(
        f"{base_url}/api/items/root:/{item_id}.md:/content",
        headers={"Accept": "application/json", "X-API-AUTH": session},
        method="GET",
    )
    status, body = _open_request(request)
    assert status == 200, f"Expected 200 for item {item_id}, got {status}: {body}"
    return body


def test_fixture_inventory_is_non_empty(seeded_items: dict[str, list[dict[str, str]]]) -> None:
    assert seeded_items["notebooks"]
    assert seeded_items["notes"]
    assert seeded_items["tags"]
    assert seeded_items["note_tags"]


@pytest.mark.parametrize(
    "notebook",
    EXPECTED_ITEMS["notebooks"],
    ids=lambda item: f"notebook:{item['path']}",
)
def test_seeded_notebook_exists(
    notebook: dict[str, str],
    joplin_base_url: str,
    session_id: str,
) -> None:
    content = _fetch_item_content(joplin_base_url, session_id, notebook["id"])
    assert "type_: 2" in content
    assert content.splitlines()[0] == notebook["title"]


@pytest.mark.parametrize(
    "note",
    EXPECTED_ITEMS["notes"],
    ids=lambda item: f"note:{item['notebook_path']}/{item['slug']}",
)
def test_seeded_note_exists(
    note: dict[str, str],
    joplin_base_url: str,
    session_id: str,
) -> None:
    content = _fetch_item_content(joplin_base_url, session_id, note["id"])
    assert "type_: 1" in content
    assert content.splitlines()[0] == note["title"]
    assert f"parent_id: {note['parent_id']}" in content


@pytest.mark.parametrize(
    "tag",
    EXPECTED_ITEMS["tags"],
    ids=lambda item: f"tag:{item['title']}",
)
def test_seeded_tag_exists(
    tag: dict[str, str],
    joplin_base_url: str,
    session_id: str,
) -> None:
    content = _fetch_item_content(joplin_base_url, session_id, tag["id"])
    assert "type_: 5" in content
    assert content.splitlines()[0] == tag["title"]


@pytest.mark.parametrize(
    "note_tag",
    EXPECTED_ITEMS["note_tags"],
    ids=lambda item: f"note-tag:{item['id']}",
)
def test_seeded_note_tag_exists(
    note_tag: dict[str, str],
    joplin_base_url: str,
    session_id: str,
) -> None:
    content = _fetch_item_content(joplin_base_url, session_id, note_tag["id"])
    assert "type_: 6" in content
    assert f"note_id: {note_tag['note_id']}" in content
    assert f"tag_id: {note_tag['tag_id']}" in content