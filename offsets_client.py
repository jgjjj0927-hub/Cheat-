# language: python, file: offsets_client.py — pull offsets.json from raw.githubusercontent
import os
import sys
import json
import requests

GH_REPO = os.environ.get("GH_REPO", "jgjjj0927-hub/Cheat-")
GH_BRANCH = os.environ.get("GH_BRANCH", "main")
RAW_URL = f"https://raw.githubusercontent.com/{GH_REPO}/{GH_BRANCH}/offsets.json"

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OFFSETS_PATH = os.path.join(BASE_DIR, "offsets.json")


def pull(timeout=5):
    try:
        r = requests.get(RAW_URL, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        if not isinstance(data, dict):
            return None
        with open(OFFSETS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data
    except Exception:
        return None


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
