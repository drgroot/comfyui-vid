#!/usr/bin/env python3

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


RCLONE_REMOTE = os.environ.get("COMFYUI_SYNC_RCLONE_REMOTE", "b2")
SERVER_HOST = os.environ.get("COMFYUI_SYNC_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("COMFYUI_SYNC_SERVER_PORT", "8189"))
MAX_JOBS = int(os.environ.get("COMFYUI_SYNC_MAX_JOBS", "3"))
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_COMFYUI_DIRADADS", "/ComfyUI")).resolve()

RCLONE_FLAGS = [
    "--checkers=4",
    "--multi-thread-cutoff=64M",
    "--multi-thread-streams=4",
    "--buffer-size=16M",
    "--retries=3",
    "--low-level-retries=10",
    "--stats=0",
]


def _normalize_file_path(file_name: str) -> Path:
    relative_path = Path(file_name.strip())
    if not file_name.strip():
        raise ValueError("path is empty")
    if relative_path.is_absolute():
        raise ValueError("absolute paths are not allowed")
    if any(part in ("", ".", "..") for part in relative_path.parts):
        raise ValueError("path must not contain empty, '.', or '..' segments")
    return relative_path


def _copy_one(file_name: str) -> dict:
    try:
        relative_path = _normalize_file_path(file_name)
    except ValueError as exc:
        return {"file": file_name, "status": "invalid", "detail": str(exc)}

    destination = (WORKSPACE_DIR / relative_path).resolve()
    try:
        destination.relative_to(WORKSPACE_DIR)
    except ValueError:
        return {"file": file_name, "status": "invalid", "detail": "path escapes workspace"}

    if destination.exists():
        return {"file": file_name, "status": "skipped", "detail": "already exists"}

    destination.parent.mkdir(parents=True, exist_ok=True)
    remote_path = f"{RCLONE_REMOTE}:servc-gen/{relative_path.as_posix()}"
    command = ["rclone", "copyto", *RCLONE_FLAGS, remote_path, str(destination)]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return {
            "file": file_name,
            "status": "error",
            "detail": (completed.stderr or completed.stdout).strip() or "rclone failed",
        }

    if not destination.exists():
        return {"file": file_name, "status": "error", "detail": "copy completed but file is missing"}

    return {"file": file_name, "status": "copied"}


def _coerce_files(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError("'files' must be a string or a list of strings")


def _parse_request_files(handler: BaseHTTPRequestHandler) -> list[str]:
    parsed = urlparse(handler.path)
    query = parse_qs(parsed.query, keep_blank_values=True)
    files: list[str] = query.get("files", [])

    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    if content_length <= 0:
        return files

    body = handler.rfile.read(content_length)
    if not body:
        return files

    content_type = handler.headers.get("Content-Type", "")
    if "application/json" in content_type:
        payload = json.loads(body.decode("utf-8"))
        body_files = _coerce_files(payload.get("files") if isinstance(payload, dict) else payload)
    elif "application/x-www-form-urlencoded" in content_type:
        payload = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        body_files = payload.get("files", [])
    else:
        try:
            payload = json.loads(body.decode("utf-8"))
            body_files = _coerce_files(payload.get("files") if isinstance(payload, dict) else payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"unsupported payload format: {exc}") from exc

    return files + body_files


class SyncRequestHandler(BaseHTTPRequestHandler):
    server_version = "ComfyUISyncServer/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        try:
            requested_files = _parse_request_files(self)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        if not requested_files:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "provide at least one 'files' entry"})
            return

        deduped_files = list(dict.fromkeys(requested_files))
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=max(1, MAX_JOBS)) as executor:
            future_map = {executor.submit(_copy_one, file_name): file_name for file_name in deduped_files}
            for future in as_completed(future_map):
                results.append(future.result())

        results.sort(key=lambda item: deduped_files.index(item["file"]))
        failed = [item for item in results if item["status"] in {"error", "invalid"}]
        status_code = HTTPStatus.OK if not failed else HTTPStatus.MULTI_STATUS

        self._send_json(
            status_code,
            {
                "workspace": str(WORKSPACE_DIR),
                "remote": RCLONE_REMOTE,
                "results": results,
            },
        )

    def log_message(self, format: str, *args):
        print(format % args, flush=True)

    def _send_json(self, status_code: HTTPStatus, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), SyncRequestHandler) as server:
        print(
            f"workspace sync server listening on {SERVER_HOST}:{SERVER_PORT}, "
            f"workspace={WORKSPACE_DIR}, remote={RCLONE_REMOTE}, max_jobs={MAX_JOBS}",
            flush=True,
        )
        server.serve_forever()


if __name__ == "__main__":
    main()
