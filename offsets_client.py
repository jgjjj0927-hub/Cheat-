# language: python, file: offsets_client.py — pull offsets.json from Cheat-
import os
import sys
import json
import base64
import requests

GH_REPO = os.environ.get("GH_REPO", "jgjjj0927-hub/Cheat-")
GH_BRANCH = os.environ.get("GH_BRANCH", "main")
GH_TOKEN = os.environ.get("GH_TOKEN", "")

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OFFSETS_PATH = os.path.join(BASE_DIR, "offsets.json")


def _api_url():
    return f"https://api.github.com/repos/{GH_REPO}/contents/offsets.json"


def _raw_url():
    return f"https://raw.githubusercontent.com/{GH_REPO}/{GH_BRANCH}/offsets.json"


def _headers():
    h = {"Accept": "application/vnd.github+json"}
    if GH_TOKEN:
        h["Authorization"] = f"Bearer {GH_TOKEN}"
    return h


def pull(timeout=5):
    data = None
    if GH_TOKEN:
        try:
            r = requests.get(_api_url(), headers=_headers(),
                             params={"ref": GH_BRANCH}, timeout=timeout)
            if r.status_code == 200:
                payload = r.json()
                data = json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
        except Exception:
            data = None
    if data is None:
        try:
            r = requests.get(_raw_url(), timeout=timeout)
            if r.status_code == 200:
                data = r.json()
        except Exception:
            data = None
    if not isinstance(data, dict):
        return None
    try:
        with open(OFFSETS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
    return data


def load(use_cache=True):
    if use_cache and os.path.exists(OFFSETS_PATH):
        try:
            with open(OFFSETS_PATH, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return pull() or {}
