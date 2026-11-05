# language: python, file: cheat.py — CS2 external, full
import time
import threading
import math
import json
import os
import sys
import ctypes
from ctypes import wintypes

import pymem
import pymem.process
import win32api
import win32con

try:
    from offsets import *
except ImportError:
    pass

try:
    from offsets_client import load as _load_offsets
    _REMOTE = _load_offsets()
except Exception:
    _REMOTE = {}

_ALLOWED_PREFIX = ("DW_", "M_", "BONE_")
for _k, _v in _REMOTE.items():
    if not any(_k.startswith(p) for p in _ALLOWED_PREFIX):
        continue
    if not isinstance(_v, int):
        continue
    globals()[_k] = _v

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

try:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        CFG = json.load(f)
except Exception:
    CFG = {}

_save_pending = threading.Event()

def save_config():
    _save_pending.set()

def _save_worker():
    while True:
        _save_pending.wait()
        _save_pending.clear()
        time.sleep(0.5)
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(CFG, f, indent=2)
        except Exception:
            pass

threading.Thread(target=_save_worker, daemon=True).start()

SCREEN_W = ctypes.windll.user32.GetSystemMetrics(0)
SCREEN_H = ctypes.windll.user32.GetSystemMetrics(1)


class Memory:
    def __init__(self):
        self.pm = None
        self.client = 0
        self.pid = 0
        self.ready = False

    def attach(self):
        try:
            self.pm = pymem.Pymem("cs2.exe")
            self.pid = self.pm.process_id
            mod = pymem.process.module_from_name(self.pm.process_handle, "client.dll")
            if not mod:
                self.ready = False
                return False
            self.client = mod.lpBaseOfDll
            self.ready = True
            return True
        except Exception:
            self.pm = None
            self.ready = False
            return False

    def _read(self, fn, addr, default):
        try:
            if not self.pm or fn is None:
                return default
            return fn(addr)
        except (pymem.exception.MemoryReadError, pymem.exception.ProcessError):
            self.ready = False
            return default

    def read_int(self, addr):
        return self._read(self.pm.read_int if self.pm else None, addr, 0)

    def read_bool(self, addr):
        return self._read(self.pm.read_bool if self.pm else None, addr, False)

    def read_ptr(self, addr):
        return self._read(self.pm.read_longlong if self.pm else None, addr, 0)

    def read_float(self, addr):
        return self._read(self.pm.read_float if self.pm else None, addr, 0.0)

    def read_vec3(self, addr):
        if not self.pm:
            return (0.0, 0.0, 0.0)
        try:
            return (self.pm.read_float(addr),
                    self.pm.read_float(addr + 4),
                    self.pm.read_float(addr + 8))
        except Exception:
            self.ready = False
            return (0.0, 0.0, 0.0)

    def read_matrix(self, addr):
        if not self.pm:
            return [0.0] * 16
        try:
            return [self.pm.read_float(addr + i * 4) for i in range(16)]
        except Exception:
            self.ready = False
            return [0.0] * 16

    def read_bone(self, pawn, bone_id):
        if not self.pm or not pawn:
            return (0.0, 0.0, 0.0)
        try:
            scene = self.pm.read_longlong(pawn + M_P_GAME_SCENE_NODE)
            if not scene:
                return (0.0, 0.0, 0.0)
            model = self.pm.read_longlong(scene + M_MODEL_STATE)
            if not model:
                return (0.0, 0.0, 0.0)
            bone_ptr = model + M_BONE_ARRAY + bone_id * 32
            return (self.pm.read_float(bone_ptr),
                    self.pm.read_float(bone_ptr + 4),
                    self.pm.read_float(bone_ptr + 8))
        except Exception:
            return (0.0, 0.0, 0.0)


mem = Memory()
overlay_data = {"boxes": [], "texts": [], "radar": [], "skeleton": [],
                "ready": False, "pid": 0, "bomb": None, "spectators": []}
overlay_lock = threading.Lock()


def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

def vec_len(a):
    return math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)

def dist(a, b):
    return vec_len(vec_sub(a, b))

def world_to_screen(pos, mat, w, h):
    cw = mat[12] * pos[0] + mat[13] * pos[1] + mat[14] * pos[2] + mat[15]
    if cw < 0.001:
        return None
    cx = mat[0] * pos[0] + mat[1] * pos[1] + mat[2] * pos[2] + mat[3]
    cy = mat[4] * pos[0] + mat[5] * pos[1] + mat[6] * pos[2] + mat[7]
    nx, ny = cx / cw, cy / cw
    if not (math.isfinite(nx) and math.isfinite(ny)):
        return None
    return ((w / 2) * (nx + 1), (h / 2) * (1 - ny))

def calc_angle(src, dst):
    d = vec_sub(dst, src)
    hyp = math.sqrt(d[0] ** 2 + d[1] ** 2)
    ax = -math.degrees(math.atan2(d[2], hyp)) if hyp != 0 else 0.0
    ay = math.degrees(math.atan2(d[1], d[0]))
    return (ax, ay, 0.0)

def angle_dist(a, b):
    dx = math.remainder(a[0] - b[0], 360.0)
    dy = math.remainder(a[1] - b[1], 360.0)
    return math.sqrt(dx * dx + dy * dy)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

def send_mouse(flags):
    inp = INPUT(type=0)
    inp.mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def send_key(vk, up=False):
    inp = INPUT(type=1)
    inp.ki = KEYBDINPUT(vk, 0, 0x0002 if up else 0, 0, None)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def read_entity(pawn):
    if not pawn:
        return None
    hp = mem.read_int(pawn + M_I_HEALTH)
    team = mem.read_int(pawn + M_I_TEAM_NUM)
    life = mem.read_int(pawn + M_LIFE_STATE)
    dormant = mem.read_bool(pawn + M_B_DORMANT)
    origin = mem.read_vec3(pawn + M_VEC_ORIGIN)
    view_off = mem.read_vec3(pawn + M_VEC_VIEW_OFFSET)
    head = (origin[0], origin[1], origin[2] + view_off[2])
    spotted = mem.read_bool(pawn + M_B_SPOTTED)
    return {"pawn": pawn, "origin": origin, "head": head, "hp": hp,
            "team": team, "life": life, "dormant": dormant, "spotted": spotted}

def get_entities():
    if not mem.ready:
        return None, []
    el = mem.read_ptr(mem.client + DW_ENTITY_LIST)
    if not el:
        return None, []
    lp = mem.read_ptr(mem.client + DW_LOCAL_PLAYER_PAWN)
    if not lp:
        return None, []
    me = read_entity(lp)
    if not me:
        return None, []
    ents = []
    for i in range(1, 65):
        try:
            entry = mem.read_ptr(el + 0x10 + 8 * (i >> 9))
            if not entry:
                continue
            pawn = mem.read_ptr(entry + 0x78 * (i & 0x1FF))
            if not pawn or pawn == lp:
                continue
            e = read_entity(pawn)
            if not e or e["hp"] <= 0 or e["life"] != 0 or e["dormant"]:
                continue
            if e["team"] not in (2, 3):
                continue
            ents.append(e)
        except Exception:
            continue
    return me, ents

def get_weapon(pawn):
    wpn = mem.read_ptr(pawn + M_P_CLIPPING_WEAPON)
    if not wpn:
        return None
    idx = mem.read_int(wpn + M_I_ITEM_DEFINITION_INDEX)
    return idx if idx > 0 else None

def get_bomb():
    el = mem.read_ptr(mem.client + DW_ENTITY_LIST)
    if not el:
        return None
    for i in range(1, 65):
        try:
            entry = mem.read_ptr(el + 0x10 + 8 * (i >> 9))
            if not entry:
                continue
            ent = mem.read_ptr(entry + 0x78 * (i & 0x1FF))
            if not ent:
                continue
            if mem.read_bool(ent + M_B_BOMB_PLANTED):
                blow = mem.read_float(ent + M_FL_C4_BLOW)
                remain = max(0.0, blow - time.time())
                return {"remaining": remain}
        except Exception:
            continue
    return None

def get_spectators(me, ents):
    out = []
    for e in ents:
        try:
            obs = mem.read_int(e["pawn"] + M_H_OBSERVER_TARGET)
            if obs == me["pawn"]:
                out.append(e)
        except Exception:
            continue
    return out

def compute_overlay():
    me, ents = get_entities()
    if me is None or not mem.ready:
        with overlay_lock:
            overlay_data["ready"] = mem.ready
            overlay_data["pid"] = mem.pid
        return
    view = mem.read_matrix(mem.client + DW_VIEW_MATRIX)
    boxes, texts, radar, skeleton = [], [], [], []
    for e in ents:
        if not CFG.get("esp_team", False) and e["team"] == me["team"]:
            continue
        d = dist(me["origin"], e["origin"])
        if d > CFG.get("esp_max_dist", 2000):
            continue
        hs = world_to_screen(e["head"], view, SCREEN_W, SCREEN_H)
        fs = world_to_screen(e["origin"], view, SCREEN_W, SCREEN_H)
        if hs and fs:
            boxes.append((hs[0], hs[1], fs[0], fs[1], e["hp"]))
            if CFG.get("esp_name", True):
                texts.append((hs[0], hs[1] - 16, "enemy"))
            if CFG.get("esp_distance", True):
                texts.append((hs[0], fs[1] + 2, f"{d / 100:.0f}m"))
            if CFG.get("esp_weapon", False):
                wi = get_weapon(e["pawn"])
                if wi:
                    texts.append((hs[0], hs[1] - 30, f"wpn:{wi}"))
        if CFG.get("esp_skeleton", False):
            bones = []
            for bid in (BONE_HEAD, BONE_NECK, BONE_CHEST, BONE_PELVIS):
                bp = mem.read_bone(e["pawn"], bid)
                if bp[0] or bp[1]:
                    sp = world_to_screen(bp, view, SCREEN_W, SCREEN_H)
                    if sp:
                        bones.append(sp)
            if len(bones) >= 2:
                skeleton.append(bones)
        rx = (e["origin"][0] - me["origin"][0]) * 0.05
        ry = (e["origin"][1] - me["origin"][1]) * 0.05
        radar.append((rx, ry, e["team"] == me["team"]))
    bomb = get_bomb() if CFG.get("bomb_enabled", True) else None
    specs = get_spectators(me, ents) if CFG.get("spectator_enabled", True) else []
    with overlay_lock:
        overlay_data.update({
            "boxes": boxes, "texts": texts, "radar": radar, "skeleton": skeleton,
            "ready": mem.ready, "pid": mem.pid, "bomb": bomb,
            "spectators": [s["pawn"] for s in specs],
        })

def aimbot_tick():
    if not CFG.get("aimbot_enabled", False) or not mem.ready:
        return
    if not (win32api.GetAsyncKeyState(CFG.get("aimbot_key", 0x02)) & 0x8000):
        return
    me, ents = get_entities()
    if not me:
        return
    va = mem.read_vec3(mem.client + DW_VIEW_ANGLES)
    best = None
    best_score = 1e9
    for e in ents:
        if not CFG.get("aimbot_team", False) and e["team"] == me["team"]:
            continue
        if CFG.get("aimbot_visible", False) and not e["spotted"]:
            continue
        tgt = calc_angle(me["head"], e["head"])
        ad = angle_dist(va, tgt)
        if ad > CFG.get("aimbot_fov", 5.0):
            continue
        score = ad
        mode = CFG.get("aimbot_mode", "crosshair")
        if mode == "hp":
            score = e["hp"]
        elif mode == "distance":
            score = dist(me["origin"], e["origin"])
        if score < best_score:
            best_score = score
            best = tgt
    if best:
        smooth = max(1.0, CFG.get("aimbot_smooth", 1.0))
        nva = (va[0] + (best[0] - va[0]) / smooth,
               va[1] + (best[1] - va[1]) / smooth, 0.0)
        try:
            mem.pm.write_float(mem.client + DW_VIEW_ANGLES, nva[0])
            mem.pm.write_float(mem.client + DW_VIEW_ANGLES + 4, nva[1])
        except Exception:
            pass

def trigger_tick():
    if not CFG.get("trigger_enabled", False) or not mem.ready:
        return
    me, ents = get_entities()
    if not me:
        return
    va = mem.read_vec3(mem.client + DW_VIEW_ANGLES)
    for e in ents:
        if e["team"] == me["team"]:
            continue
        tgt = calc_angle(me["head"], e["head"])
        if angle_dist(va, tgt) <= CFG.get("trigger_fov", 2.0):
            send_mouse(0x0002)
            time.sleep(0.01)
            send_mouse(0x0004)
            time.sleep(CFG.get("trigger_delay", 30) / 1000.0)
            break

def movement_tick():
    if not mem.ready:
        return
    me, _ = get_entities()
    if not me or not me["pawn"]:
        return
    if CFG.get("no_recoil", False):
        punch = mem.read_vec3(me["pawn"] + M_AIM_PUNCH_ANGLE)
        if punch[0] or punch[1]:
            va = mem.read_vec3(mem.client + DW_VIEW_ANGLES)
            try:
                mem.pm.write_float(mem.client + DW_VIEW_ANGLES, va[0] - punch[0] * 2.0)
                mem.pm.write_float(mem.client + DW_VIEW_ANGLES + 4, va[1] - punch[1] * 2.0)
            except Exception:
                pass
    if CFG.get("bhop_enabled", False) and (win32api.GetAsyncKeyState(win32con.VK_SPACE) & 0x8000):
        flags = mem.read_int(me["pawn"] + M_F_FLAGS)
        if flags & 1:
            send_key(win32con.VK_SPACE, False)
            send_key(win32con.VK_SPACE, True)

def cheat_loop():
    while True:
        if not mem.ready:
            if not mem.attach():
                with overlay_lock:
                    overlay_data["ready"] = False
                time.sleep(2.0)
                continue
        try:
            compute_overlay()
            aimbot_tick()
            trigger_tick()
            movement_tick()
        except Exception:
            mem.ready = False
        time.sleep(0.05)

def start_cheat():
    t = threading.Thread(target=cheat_loop, daemon=True)
    t.start()
    return t
