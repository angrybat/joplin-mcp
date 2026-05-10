"""Seed Joplin Server from canonical fixture definitions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


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

        notes.append(
            {
                "source_path": source_path,
                "notebook_path": notebook_path,
                "slug": slug,
                "title": str(parsed["title"]),
                "created": str(parsed["created"]),
                "updated": str(parsed["updated"]),
                "tags": sorted(str(tag) for tag in tags),
                "body": str(parsed["body"]),
            }
        )

    notes.sort(key=lambda item: (item["notebook_path"], item["slug"]))
    return notes


def stable_id(prefix: str, value: str) -> str:
    return hashlib.sha256(f"{prefix}:{value}".encode("utf-8")).hexdigest()[:32]


def render_prop(name: str, value: object) -> str:
    text = str(value)
    return f"{name}: {text}" if text else f"{name}:"


def render_folder_content(folder_id: str, parent_id: str, title: str, timestamp: str) -> str:
    props = [
        render_prop("id", folder_id),
        render_prop("created_time", timestamp),
        render_prop("updated_time", timestamp),
        render_prop("user_created_time", timestamp),
        render_prop("user_updated_time", timestamp),
        render_prop("encryption_cipher_text", ""),
        render_prop("encryption_applied", 0),
        render_prop("parent_id", parent_id),
        render_prop("is_shared", 0),
        render_prop("share_id", ""),
        render_prop("user_data", ""),
        render_prop("type_", 2),
    ]
    return f"{title}\n\n" + "\n".join(props)


def render_note_content(note_id: str, parent_id: str, title: str, body: str, created: str, updated: str) -> str:
    props = [
        render_prop("id", note_id),
        render_prop("parent_id", parent_id),
        render_prop("created_time", created),
        render_prop("updated_time", updated),
        render_prop("is_conflict", 0),
        render_prop("latitude", "0.00000000"),
        render_prop("longitude", "0.00000000"),
        render_prop("altitude", "0.0000"),
        render_prop("author", ""),
        render_prop("source_url", ""),
        render_prop("is_todo", 0),
        render_prop("todo_due", 0),
        render_prop("todo_completed", 0),
        render_prop("source", "joplin-mcp-fixtures"),
        render_prop("source_application", "net.cozic.joplindev-desktop"),
        render_prop("application_data", ""),
        render_prop("order", 0),
        render_prop("user_created_time", created),
        render_prop("user_updated_time", updated),
        render_prop("encryption_cipher_text", ""),
        render_prop("encryption_applied", 0),
        render_prop("markup_language", 1),
        render_prop("is_shared", 0),
        render_prop("share_id", ""),
        render_prop("conflict_original_id", ""),
        render_prop("master_key_id", ""),
        render_prop("user_data", ""),
        render_prop("deleted_time", 0),
        render_prop("type_", 1),
    ]
    return f"{title}\n\n{body.rstrip()}\n\n" + "\n".join(props)


def render_tag_content(tag_id: str, title: str, timestamp: str) -> str:
    props = [
        render_prop("id", tag_id),
        render_prop("created_time", timestamp),
        render_prop("updated_time", timestamp),
        render_prop("user_created_time", timestamp),
        render_prop("user_updated_time", timestamp),
        render_prop("encryption_cipher_text", ""),
        render_prop("encryption_applied", 0),
        render_prop("is_shared", 0),
        render_prop("parent_id", ""),
        render_prop("user_data", ""),
        render_prop("type_", 5),
    ]
    return f"{title}\n\n" + "\n".join(props)


def render_note_tag_content(note_tag_id: str, note_id: str, tag_id: str, timestamp: str) -> str:
    props = [
        render_prop("id", note_tag_id),
        render_prop("note_id", note_id),
        render_prop("tag_id", tag_id),
        render_prop("created_time", timestamp),
        render_prop("updated_time", timestamp),
        render_prop("user_created_time", timestamp),
        render_prop("user_updated_time", timestamp),
        render_prop("encryption_cipher_text", ""),
        render_prop("encryption_applied", 0),
        render_prop("is_shared", 0),
        render_prop("type_", 6),
    ]
    return "\n\n" + "\n".join(props)


def session_request(base_url: str, email: str, password: str) -> urllib.request.Request:
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    return urllib.request.Request(
        f"{base_url}/api/sessions",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )


def json_request(
    base_url: str,
    path: str,
    session_id: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> urllib.request.Request:
    data = None
    headers = {"Accept": "application/json", "X-API-AUTH": session_id}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)


def decode_response(response) -> tuple[int, str]:
    body = response.read().decode("utf-8")
    return response.getcode(), body


def open_request(request: urllib.request.Request) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return decode_response(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return error.code, body


def wait_for_session(base_url: str, email: str, password: str, attempts: int, retry_seconds: float) -> str:
    last_status = 0
    last_body = ""
    for attempt in range(1, attempts + 1):
        status, body = open_request(session_request(base_url, email, password))
        last_status = status
        last_body = body
        if status == 200:
            payload = json.loads(body)
            session_id = payload.get("id")
            if not session_id:
                raise RuntimeError("Session response did not include an id")
            print(f"Authenticated with Joplin Server on attempt {attempt}")
            return str(session_id)
        if status == 403:
            raise RuntimeError("Joplin Server rejected admin login for admin@localhost")
        time.sleep(retry_seconds)

    raise RuntimeError(
        "Timed out waiting for Joplin Server session login. "
        f"Last status={last_status}, body={last_body!r}"
    )


def upload_batch(base_url: str, session_id: str, items: list[dict[str, str]], label: str) -> None:
    payload_items = [{"name": item["name"], "body": item["body"]} for item in items]
    status, body = open_request(
        json_request(
            base_url,
            "/api/batch_items",
            session_id,
            method="PUT",
            payload={"items": payload_items},
        )
    )
    if status != 200:
        raise RuntimeError(f"Failed to upload {label}: HTTP {status} body={body!r}")

    payload = json.loads(body)
    results = payload.get("items", {})
    failures = []
    for item in items:
        result = results.get(item["name"], {})
        error = result.get("error")
        if error:
            failures.append(f"{item['name']}: {error}")
    if failures:
        raise RuntimeError(f"Failed to upload {label}: {'; '.join(failures)}")

    print(f"Uploaded {len(items)} {label}")


def fetch_item_content(base_url: str, session_id: str, item_id: str) -> str:
    request = json_request(base_url, f"/api/items/root:/{item_id}.md:/content", session_id)
    status, body = open_request(request)
    if status != 200:
        raise RuntimeError(f"Failed to verify item {item_id}: HTTP {status} body={body!r}")
    return body


def build_seed_plan(notes: list[dict[str, object]]) -> dict[str, list[dict[str, str]]]:
    folder_rows: dict[str, dict[str, str]] = {}
    note_rows: list[dict[str, str]] = []
    tag_rows: dict[str, dict[str, str]] = {}
    note_tag_rows: list[dict[str, str]] = []

    for note in notes:
        notebook_path = str(note["notebook_path"])
        created = str(note["created"])
        updated = str(note["updated"])
        if notebook_path:
            current_path = ""
            parent_id = ""
            for segment in notebook_path.split("/"):
                current_path = f"{current_path}/{segment}".strip("/")
                folder_id = stable_id("folder", current_path)
                if current_path not in folder_rows:
                    folder_rows[current_path] = {
                        "id": folder_id,
                        "name": f"{folder_id}.md",
                        "body": render_folder_content(folder_id, parent_id, segment, created),
                    }
                parent_id = folder_id
        else:
            parent_id = ""

        note_key = f"{notebook_path}/{note['slug']}" if notebook_path else str(note["slug"])
        note_id = stable_id("note", note_key)
        note["joplin_id"] = note_id
        note_rows.append(
            {
                "id": note_id,
                "name": f"{note_id}.md",
                "body": render_note_content(
                    note_id,
                    parent_id,
                    str(note["title"]),
                    str(note["body"]),
                    created,
                    updated,
                ),
            }
        )

        tags = note.get("tags", [])
        if not isinstance(tags, list):
            raise RuntimeError(f"Invalid tags payload for note {note_key}: {tags!r}")
        for tag_title in tags:
            tag_id = stable_id("tag", str(tag_title))
            if str(tag_title) not in tag_rows:
                tag_rows[str(tag_title)] = {
                    "id": tag_id,
                    "name": f"{tag_id}.md",
                    "body": render_tag_content(tag_id, str(tag_title), created),
                }
            note_tag_id = stable_id("note-tag", f"{note_id}:{tag_id}")
            note_tag_rows.append(
                {
                    "id": note_tag_id,
                    "name": f"{note_tag_id}.md",
                    "body": render_note_tag_content(note_tag_id, note_id, tag_id, created),
                }
            )

    folders = [folder_rows[key] for key in sorted(folder_rows, key=lambda path: (path.count("/"), path))]
    tags = [tag_rows[key] for key in sorted(tag_rows)]
    note_tags = sorted(note_tag_rows, key=lambda row: row["id"])

    return {
        "folders": folders,
        "notes": note_rows,
        "tags": tags,
        "note_tags": note_tags,
    }


def verify_seed(base_url: str, session_id: str, plan: dict[str, list[dict[str, str]]]) -> None:
    if plan["folders"]:
        folder_id = plan["folders"][0]["id"]
        content = fetch_item_content(base_url, session_id, folder_id)
        if "type_: 2" not in content:
            raise RuntimeError(f"Folder verification failed for {folder_id}")

    if plan["notes"]:
        note_id = plan["notes"][0]["id"]
        content = fetch_item_content(base_url, session_id, note_id)
        if "type_: 1" not in content:
            raise RuntimeError(f"Note verification failed for {note_id}")

    if plan["tags"]:
        tag_id = plan["tags"][0]["id"]
        content = fetch_item_content(base_url, session_id, tag_id)
        if "type_: 5" not in content:
            raise RuntimeError(f"Tag verification failed for {tag_id}")

    print(
        "Verified seeded content: "
        f"{len(plan['folders'])} folders, {len(plan['notes'])} notes, "
        f"{len(plan['tags'])} tags, {len(plan['note_tags'])} note-tag links"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures-root", required=True)
    parser.add_argument("--joplin-base-url", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--max-attempts", type=int, default=45)
    parser.add_argument("--retry-seconds", type=float, default=2.0)
    args = parser.parse_args()

    notes = read_markdown_definitions(Path(args.fixtures_root) / "definitions")
    plan = build_seed_plan(notes)
    session_id = wait_for_session(
        args.joplin_base_url,
        args.admin_email,
        args.admin_password,
        args.max_attempts,
        args.retry_seconds,
    )

    upload_batch(args.joplin_base_url, session_id, plan["folders"], "folders")
    upload_batch(args.joplin_base_url, session_id, plan["notes"], "notes")
    upload_batch(args.joplin_base_url, session_id, plan["tags"], "tags")
    upload_batch(args.joplin_base_url, session_id, plan["note_tags"], "note-tag links")
    verify_seed(args.joplin_base_url, session_id, plan)


if __name__ == "__main__":
    main()