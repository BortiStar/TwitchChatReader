import io
import urllib.request
from collections import OrderedDict

from PIL import Image, ImageTk


class EmoteRenderer:
    """
    Ленивый кэш emote-картинок с ограничением размера.
    Загружает картинку только при первом обращении к токену.
    Потокобезопасен для чтения (используется из Tk-потока).
    """

    MAX_CACHE = 300

    def __init__(self, tk_master):
        self._master = tk_master
        self._cache = OrderedDict()   # token -> ImageTk.PhotoImage
        self._map = {}                # token -> url

    def set_map(self, mapping: dict):
        self._map = mapping or {}

    def get(self, token: str):
        """Возвращает ImageTk.PhotoImage или None, если токен не эмот."""
        url = self._map.get(token)
        if not url:
            return None
        if token in self._cache:
            # обновляем порядок LRU
            self._cache.move_to_end(token)
            return self._cache[token]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=5).read()
            img = Image.open(io.BytesIO(raw))
            photo = ImageTk.PhotoImage(img, master=self._master)
            self._cache[token] = photo
            if len(self._cache) > self.MAX_CACHE:
                self._cache.popitem(last=False)
            return photo
        except Exception:
            return None

    def clear(self):
        self._cache.clear()
        self._map = {}