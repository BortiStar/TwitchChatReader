import os
import json
import re
import urllib.request
import urllib.parse
from PIL import ImageColor

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(APP_DIR, "assets")
SKINS_DIR = os.path.join(APP_DIR, "skins")
WISHLIST_FILE = os.path.join(APP_DIR, "wishlist.json")

ACTIVE_SKIN = "default"

BTTV_GLOBAL_URL = "https://api.betterttv.net/3/cached/emotes/global"
FFZ_GLOBAL_URL = "https://api.frankerfacez.com/v1/set/global"
FFZ_CHANNEL_URL = "https://api.frankerfacez.com/v1/room/{}"
SEVENTV_GLOBAL_URL = "https://7tv.io/v3/emote-sets/global"

SKIN_DEFAULTS = {
    "name": "Winamp Orange",
    "background": "skins",   
    "orange": "#FF8C00",
    "orange2": "#FFB000",
    "amber": "#FFD27A",
    "black": "#101010",
    "dark": "#161616",
    "panel": "#1E1E1E",
    "panel2": "#262626",
    "line": "#3A3A3A",
    "text": "#FFF4E5",
    "muted": "#9A9288",
    "hover": "#FFA733",
    "button_hover": "#333333",
}

def asset(name):
    if not name:
        return None
    p1 = os.path.join(ASSETS_DIR, name)
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(SKINS_DIR, name)
    if os.path.exists(p2):
        return p2
    return None

def load_skin_assets(skin_name=ACTIVE_SKIN):
    assets = {}
    dirs = [SKINS_DIR, os.path.join(SKINS_DIR, skin_name)]
    for d in dirs:
        if not os.path.isdir(d):
            continue
        try:
            for f in sorted(os.listdir(d)):
                if f.lower().endswith(".png"):
                    assets[os.path.splitext(f)[0]] = os.path.join(d, f)
        except Exception:
            pass
    return assets

def load_skin(name=ACTIVE_SKIN):
    skin = dict(SKIN_DEFAULTS)
    path = os.path.join(SKINS_DIR, name if name.endswith(".json") else name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in skin or k == "name":
                skin[k] = v
    except Exception:
        pass
    return skin

def shade(hex_color, factor):
    try:
        r, g, b = ImageColor.getrgb(hex_color)[:3]
        return "#%02x%02x%02x" % (min(255, int(r * factor)),
                                  min(255, int(g * factor)),
                                  min(255, int(b * factor)))
    except Exception:
        return hex_color

def extract_channel_name(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    text = text.replace("www.", "")
    patterns = [
        r"twitch\.tv/([a-zA-Z0-9_]+)",
        r"twitch\.tv/videos/\d+.*[?&]channel=([a-zA-Z0-9_]+)",
        r"^#?([a-zA-Z0-9_]+)$",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).lower()
    return ""

def load_wishlist():
    if not os.path.exists(WISHLIST_FILE):
        return []
    try:
        with open(WISHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [str(x).strip().lower() for x in data if str(x).strip()]
    except Exception:
        pass
    return []

def save_wishlist(items):
    try:
        with open(WISHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def http_get_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None

def fetch_emote_maps(channel_name):
    emotes = {}
    data = http_get_json(BTTV_GLOBAL_URL)
    if isinstance(data, list):
        for e in data:
            code, eid = e.get("code"), e.get("id")
            if code and eid:
                emotes[code] = f"https://cdn.betterttv.net/emote/{eid}/1x"
    data = http_get_json(FFZ_GLOBAL_URL)
    if isinstance(data, dict):
        for _, s in data.get("sets", {}).items():
            for e in s.get("emoticons", []):
                code = e.get("name")
                urls = e.get("urls", {})
                url = urls.get("1") or urls.get("2") or urls.get("4")
                if code and url:
                    if url.startswith("//"):
                        url = "https:" + url
                    emotes[code] = url
    data = http_get_json(SEVENTV_GLOBAL_URL)
    if isinstance(data, dict):
        for e in data.get("emotes", []):
            code, eid = e.get("name"), e.get("id")
            if code and eid:
                emotes[code] = f"https://cdn.7tv.app/emote/{eid}/1x"
    data = http_get_json(FFZ_CHANNEL_URL.format(urllib.parse.quote(channel_name)))
    if isinstance(data, dict):
        for _, s in data.get("sets", {}).items():
            for e in s.get("emoticons", []):
                code = e.get("name")
                urls = e.get("urls", {})
                url = urls.get("1") or urls.get("2") or urls.get("4")
                if code and url:
                    if url.startswith("//"):
                        url = "https:" + url
                    emotes[code] = url
    return emotes