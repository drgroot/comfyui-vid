#!/usr/bin/env python3

import json
import os
import stat
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


RCLONE_REMOTE = os.environ.get("COMFYUI_SYNC_RCLONE_REMOTE", "b2")
SERVER_HOST = os.environ.get("COMFYUI_SYNC_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("COMFYUI_SYNC_SERVER_PORT", "8189"))
MAX_JOBS = int(os.environ.get("COMFYUI_SYNC_MAX_JOBS", "2"))
COMFYUI_DIR = Path(os.environ.get("COMFYUI_DIR", "/ComfyUI")).resolve()
MODELS_DIR = COMFYUI_DIR / "models"

RCLONE_FLAGS = [
    "--buffer-size=64M",
    "--retries=5",
    "--low-level-retries=20",
    "--contimeout=30s",
    "--timeout=10m",
]


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if value < 1024 or unit == "PiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024


def _rclone_status(proc_root: Path = Path("/proc")) -> dict:
    """Inspect this PID namespace without invoking ps, lsof, or rclone RC.

    Open writable model files include rclone's temporary .partial files.
    Sizes describe files on disk, not transferred bytes: rclone can preallocate.
    """
    processes = []
    inaccessible = 0
    models = MODELS_DIR.resolve()
    for process_dir in proc_root.iterdir():
        if not process_dir.name.isdigit():
            continue
        try:
            if process_dir.joinpath("comm").read_text().strip() != "rclone":
                continue
        except PermissionError:
            inaccessible += 1
            continue
        except OSError:
            continue  # Processes can exit during enumeration.

        process = {"pid": int(process_dir.name), "files": [], "inspection": "ok"}
        files = {}
        try:
            for descriptor in process_dir.joinpath("fd").iterdir():
                try:
                    info = process_dir.joinpath("fdinfo", descriptor.name).read_text()
                    flags = next(line.split()[1] for line in info.splitlines()
                                 if line.startswith("flags:"))
                    if int(flags, 8) & os.O_ACCMODE == os.O_RDONLY:
                        continue
                    target = Path(os.readlink(descriptor))
                    relative = target.relative_to(models)
                    file_stat = descriptor.stat()
                    if not stat.S_ISREG(file_stat.st_mode):
                        continue
                    files[str(relative)] = {
                        "file": str(relative),
                        "size_bytes": file_stat.st_size,
                        "size": _human_size(file_stat.st_size),
                        "allocated_bytes": file_stat.st_blocks * 512,
                        "allocated": _human_size(file_stat.st_blocks * 512),
                    }
                except PermissionError:
                    process["inspection"] = "partial"
                except (OSError, ValueError, StopIteration):
                    continue  # Closed descriptors, pipes, or non-model files.
        except OSError:
            process["inspection"] = "unavailable"

        # Both launchers put source and destination last. This is a fallback
        # label before the output is opened, not a general rclone CLI parser.
        try:
            args = os.fsdecode(process_dir.joinpath("cmdline").read_bytes()).rstrip("\0").split("\0")
            if len(args) >= 4 and args[1] in {"copy", "copyto"}:
                source, destination = args[-2:]
                if ":" in source and destination.startswith("/"):
                    target = Path(destination)
                    if args[1] == "copy":
                        target /= Path(source.split(":", 1)[1]).name
                    process["requested_file"] = str(target.resolve().relative_to(models))
        except (OSError, ValueError):
            pass
        process["files"] = [files[key] for key in sorted(files)]
        if not files:
            process["detail"] = "No writable model file visible (starting, idle, finishing, or inaccessible)."
        processes.append(process)

    return {
        "processes": sorted(processes, key=lambda item: item["pid"]),
        "inaccessible_processes": inaccessible,
        "note": "Visible rclone processes in this container; files are writable files under the models directory. Sizes may be preallocated and are not download progress percentages.",
    }


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

    destination = (MODELS_DIR / relative_path).resolve()
    try:
        destination.relative_to(MODELS_DIR)
    except ValueError:
        return {"file": file_name, "status": "invalid", "detail": "path escapes models directory"}

    if destination.exists():
        return {"file": file_name, "status": "skipped", "detail": "already exists"}

    destination.parent.mkdir(parents=True, exist_ok=True)
    remote_path = f"{RCLONE_REMOTE}:{relative_path.as_posix()}"
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
        if parsed.path == "/status":
            try:
                payload = _rclone_status()
            except OSError:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Linux /proc process inspection is unavailable"})
                return
            self._send_json(HTTPStatus.OK, payload)
            return
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
                "models_directory": str(MODELS_DIR),
                "remote": RCLONE_REMOTE,
                "results": results,
            },
        )

    def log_message(self, format: str, *args):
        print(format % args, flush=True)

    def _send_json(self, status_code: HTTPStatus, payload: dict):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), SyncRequestHandler) as server:
        print(
            f"workspace sync server listening on {SERVER_HOST}:{SERVER_PORT}, "
            f"models_directory={MODELS_DIR}, remote={RCLONE_REMOTE}, max_jobs={MAX_JOBS}",
            flush=True,
        )
        server.serve_forever()


if __name__ == "__main__":
    main()
