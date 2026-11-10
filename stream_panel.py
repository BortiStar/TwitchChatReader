import threading
import http.server
import socketserver
import tkinter as tk


class StreamPanel:
    """
    Встроенный Twitch-плеер через WebView + локальный HTTP-сервер,
    который отдаёт HTML и текущую громкость.
    Создаётся ТОЛЬКО при connect() — при отключении полностью уничтожается.
    """

    def __init__(self, master, channel, volume_var):
        self.volume_var = volume_var
        self.httpd = None
        self.webview = None
        self._sync_after_id = None
        self.frame = tk.Frame(master, bg="#000000", bd=0, highlightthickness=0)
        self.frame.pack(fill="both", expand=True)
        self.frame.bind("<Configure>", self._on_configure)
        self.frame.after(300, lambda: self._start_stream(channel))

    # ---------- resize sync ----------

    def _on_configure(self, event=None):
        if self.webview is None:
            return
        top = self.frame.winfo_toplevel()
        if getattr(top, "_resizing", False):
            return
        if self._sync_after_id is not None:
            try:
                self.frame.after_cancel(self._sync_after_id)
            except Exception:
                pass
        self._sync_after_id = self.frame.after(120, self._sync_bounds)

    def _sync_bounds(self):
        self._sync_after_id = None
        if self.webview is None:
            return
        try:
            top = self.frame.winfo_toplevel()
            if getattr(top, "_resizing", False):
                return
            self.frame.update_idletasks()
            self.webview.sync_bounds()
        except Exception:
            pass

    def sync_now(self):
        if self._sync_after_id is not None:
            try:
                self.frame.after_cancel(self._sync_after_id)
            except Exception:
                pass
            self._sync_after_id = None
        self._sync_bounds()

    # ---------- stream ----------

    def _start_stream(self, channel):
        # Ленивый импорт — tkwry не грузится, пока не подключились
        from tkwry import WebView

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://player.twitch.tv/js/embed/v1.js"></script>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                html, body {{ width: 100vw; height: 100vh; overflow: hidden; background-color: #000; }}
                #twitch-embed {{ width: 100%; height: 100%; }}
                iframe {{ width: 100%; height: 100%; border: none; display: block; }}
            </style>
        </head>
        <body>
            <div id="twitch-embed"></div>
            <script type="text/javascript">
                var player = new Twitch.Player("twitch-embed", {{
                    channel: "{channel}",
                    parent: ["localhost", "127.0.0.1"],
                    width: "100%",
                    height: "100%",
                    autoplay: true,
                    muted: false
                }});
                setInterval(function() {{
                    fetch('/volume')
                        .then(response => response.text())
                        .then(vol => {{
                            var targetVol = parseFloat(vol) / 100.0;
                            if (typeof player !== 'undefined' && Math.abs(player.getVolume() - targetVol) > 0.01) {{
                                player.setVolume(targetVol);
                                if (targetVol > 0) player.setMuted(false);
                            }}
                        }}).catch(e => console.log(e));
                }}, 1000);
            </script>
        </body>
        </html>
        """
        app_volume_var = self.volume_var

        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/volume':
                    self.send_response(200)
                    self.send_header("Content-type", "text/plain")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(str(int(app_volume_var.get())).encode("utf-8"))
                else:
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html_content.encode("utf-8"))

            def log_message(self, format, *args):
                pass

        try:
            socketserver.TCPServer.allow_reuse_address = True
            self.httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
            port = self.httpd.server_address[1]
            threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
            local_url = f"http://127.0.0.1:{port}"
            self.frame.update_idletasks()
            self.webview = WebView(self.frame, url=local_url)
            self.webview.pack(fill="both", expand=True)
            self.webview.when_failed(lambda exc: print("WebView create failed:", exc))
            self.frame.after(100, self._sync_bounds)
        except Exception as e:
            print(f"Ошибка встраивания стрима: {e}")

    # ---------- teardown ----------

    def stop(self):
        if self._sync_after_id is not None:
            try:
                self.frame.after_cancel(self._sync_after_id)
            except Exception:
                pass
            self._sync_after_id = None
        if self.webview:
            try:
                self.webview.destroy()
            except Exception:
                pass
            self.webview = None
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None
        try:
            self.frame.destroy()
        except Exception:
            pass