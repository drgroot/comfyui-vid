import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

import workspace_sync_server as sync


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.models = self.root / "models"
        self.models.mkdir()
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.patcher = patch.object(sync, "MODELS_DIR", self.models)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def process(self, pid, name="rclone", operation="copyto"):
        process = self.proc / str(pid)
        (process / "fd").mkdir(parents=True)
        (process / "fdinfo").mkdir()
        (process / "comm").write_text(name + "\n")
        destination = str(self.models / "model.bin") if operation == "copyto" else str(self.models)
        (process / "cmdline").write_bytes("\0".join([
            "rclone", operation, "--password=do-not-expose", "b2:model.bin", destination, ""
        ]).encode())
        return process

    def descriptor(self, process, fd, target, flags="0100001"):
        (process / "fd" / str(fd)).symlink_to(target)
        (process / "fdinfo" / str(fd)).write_text(f"pos:\t0\nflags:\t{flags}\n")

    def test_processes_and_partial_file_sizes(self):
        p = self.process(12)
        self.process(3, operation="copy")
        self.process(99, name="python3")
        partial = self.models / "model.bin.abcd.partial"
        partial.write_bytes(b"x" * 1536)
        self.descriptor(p, 4, partial)
        self.descriptor(p, 5, partial)  # Duplicate descriptors counted once.
        config = self.root / "rclone.conf"
        config.write_text("secret")
        self.descriptor(p, 6, config)
        self.descriptor(p, 7, self.models / "missing.partial")
        self.descriptor(p, 8, partial, "0100000")
        result = sync._rclone_status(self.proc)
        self.assertEqual([p["pid"] for p in result["processes"]], [3, 12])
        self.assertEqual(result["processes"][0]["requested_file"], "model.bin")
        files = result["processes"][1]["files"]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["size"], "1.5 KiB")
        self.assertEqual(files[0]["size_bytes"], 1536)
        self.assertEqual(files[0]["allocated_bytes"], partial.stat().st_blocks * 512)
        self.assertNotIn("do-not-expose", json.dumps(result))
        self.assertNotIn("rclone.conf", json.dumps(result))

    def test_empty_and_exited_processes(self):
        (self.proc / "123").mkdir()
        self.assertEqual(sync._rclone_status(self.proc)["processes"], [])

    def test_inaccessible_descriptors_keep_process(self):
        p = self.process(12)
        (p / "fd").rmdir()
        result = sync._rclone_status(self.proc)["processes"][0]
        self.assertEqual(result["inspection"], "unavailable")
        self.assertEqual(result["files"], [])

    def test_units(self):
        self.assertEqual(sync._human_size(0), "0 B")
        self.assertEqual(sync._human_size(1024**3), "1.0 GiB")

    @unittest.skipUnless(sys.platform == "linux", "requires Linux /proc")
    def test_live_linux_process_and_open_file(self):
        program = """
import ctypes, sys
ctypes.CDLL(None).prctl(15, b'rclone', 0, 0, 0)
with open(sys.argv[1], 'wb') as output:
    output.write(b'x' * 2048)
    output.flush()
    print('ready', flush=True)
    sys.stdin.read()
"""
        with subprocess.Popen(
            [sys.executable, "-c", program, str(self.models / "live.partial")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        ) as child:
            try:
                self.assertEqual(child.stdout.readline().strip(), "ready")
                process = next(p for p in sync._rclone_status()["processes"] if p["pid"] == child.pid)
                self.assertEqual(process["files"][0]["file"], "live.partial")
                self.assertEqual(process["files"][0]["size"], "2.0 KiB")
            finally:
                child.communicate(timeout=5)

    def test_status_http_without_auth_or_sync_side_effects(self):
        with sync.ThreadingHTTPServer(("127.0.0.1", 0), sync.SyncRequestHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(sync, "_rclone_status", return_value={"processes": []}), patch.object(sync, "_copy_one") as copy:
                    with urlopen(f"http://127.0.0.1:{server.server_port}/status?files=model.bin") as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                        self.assertEqual(json.load(response), {"processes": []})
                    copy.assert_not_called()
            finally:
                server.shutdown()
                thread.join()


if __name__ == "__main__":
    unittest.main()
