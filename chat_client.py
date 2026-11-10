import asyncio
import sys
import threading

from twitchchat import ChatMessage, TwitchChat

from emote_renderer import EmoteRenderer
from twitch_logic import fetch_emote_maps


def _run_in_thread(loop, func, *args):
    """Кросс-версионный аналог asyncio.to_thread."""
    if sys.version_info >= (3, 9):
        return asyncio.to_thread(func, *args)
    return loop.run_in_executor(None, func, *args)


class ChatClient:
    """
    Ленивый клиент Twitch-чата.
    Создаётся при connect(), уничтожается при disconnect().
    Не трогает Tk напрямую — все UI-обновления идут через textbox.after(...).
    """

    def __init__(self, channel, textbox, on_system_msg):
        self.channel = channel
        self.textbox = textbox
        self.on_system_msg = on_system_msg
        self.renderer = EmoteRenderer(tk_master=textbox)
        self._loop = None
        self._task = None
        self._thread = None
        self._running = False
        self._stopped = False

    # ---------- lifecycle ----------

    def start(self):
        if self._running or self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True,
                                        name=f"ChatClient-{self.channel}")
        self._thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._worker())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.on_system_msg(f"Критическая ошибка чата: {e}")
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for t in pending:
                    t.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None
            self._thread = None

    # ---------- main worker ----------

    async def _worker(self):
        self._task = asyncio.current_task()

        # 1) эмоты — в отдельном потоке, не блокируем event loop
        try:
            emotes = await _run_in_thread(self._loop, fetch_emote_maps, self.channel)
            if self._running:
                self.renderer.set_map(emotes or {})
                self.on_system_msg(f"Загружено смайликов: {len(emotes or {})}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.on_system_msg(f"Ошибка загрузки эмотов: {e}")

        if not self._running:
            return

        # 2) сам чат
        try:
            async with TwitchChat([self.channel]) as chat:
                async for event in chat.events(ChatMessage):
                    if not self._running:
                        break
                    self._dispatch_message(event.display_name, event.text)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if self._running:
                self.on_system_msg(f"Ошибка чата: {e}")
        finally:
            self._running = False

    # ---------- rendering ----------

    def _dispatch_message(self, nick, text):
        # Tk обновляем через after — потокобезопасно
        try:
            self.textbox.after(0, self._do_append, nick, text)
        except Exception:
            pass

    def _do_append(self, nick, text):
        if self._stopped:
            return
        tb = self.textbox
        try:
            if not tb.winfo_exists():
                return
        except Exception:
            return
        tb.configure(state="normal")
        tb.insert("end", f"{nick}: ", "nick")
        for token in text.split(" "):
            photo = self.renderer.get(token)
            if photo is not None:
                tb.image_create("end", image=photo)
                tb.insert("end", " ")
            else:
                tb.insert("end", token + " ")
        tb.insert("end", "\n")
        tb.configure(state="disabled")
        tb.see("end")

    # ---------- teardown ----------

    def stop(self):
        self._stopped = True
        self._running = False
        loop = self._loop
        task = self._task
        if loop is not None and task is not None:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except Exception:
                pass
        # не ждём поток синхронно, чтобы не фризить UI;
        # поток сам завершится и почистит loop
        self.renderer.clear()