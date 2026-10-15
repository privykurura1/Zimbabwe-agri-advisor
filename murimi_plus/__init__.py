"""Murimi Fara extras: outbreak dashboard, local-language summaries, find-help
directory, farm records and reminders, seasonal outlook, SMS channel.

Everything here is optional: app.py includes it only if it imports cleanly, so a
problem in these extras can never stop the core advisor from answering.
"""

import os as _os
import sys as _sys


def app_dir():
    """Folder holding data/, audio/ and models/: beside the exe when packaged
    (PyInstaller puts this package inside _internal), else the project folder."""
    if _os.environ.get("MURIMIFARA_APP_DIR"):
        return _os.environ["MURIMIFARA_APP_DIR"]
    if getattr(_sys, "frozen", False):
        return _os.path.dirname(_sys.executable)
    return _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
