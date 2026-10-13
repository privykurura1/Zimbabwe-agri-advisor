"""Test the human terminal flow with a pseudo terminal, including typed digest."""
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest

from challenge_agent.orchestrator import ROOT
from challenge_agent.store import Store


@unittest.skipUnless(os.name == "posix", "PTY test requires POSIX")
class HumanTerminalTests(unittest.TestCase):
    def test_interactive_review_requires_exact_confirmation(self):
        import pty
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.sqlite3"
            store = Store(path)
            draft = store.stage({"text": "Review this maize advisory", "sources": ["D1"]})
            master, slave = pty.openpty()
            try:
                proc = subprocess.Popen([sys.executable, "-m", "challenge_agent", "--db", str(path),
                                         "review", draft["id"], "--digest", draft["digest"],
                                         "--decision", "approve", "--reason", "Evidence and local context checked"],
                                        stdin=slave, stdout=slave, stderr=slave, cwd=ROOT)
                os.close(slave)
                output = b""
                deadline = time.monotonic() + 10
                while b"type APPROVE " not in output and time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        output += os.read(master, 65536)
                self.assertIn(b"type APPROVE ", output)
                self.assertIn(b"Review this maize advisory", output)
                os.write(master, ("APPROVE " + draft["digest"] + "\n").encode())
                self.assertEqual(proc.wait(timeout=5), 0)
                self.assertEqual(store.get(draft["id"])["state"], "approved")
            finally:
                os.close(master)
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
