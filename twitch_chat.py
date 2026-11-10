import os
import random
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageTk

from twitch_logic import (
    load_skin, load_skin_assets, asset, shade, extract_channel_name,
    load_wishlist, save_wishlist, ACTIVE_SKIN
)
from stream_panel import StreamPanel
from chat_client import ChatClient

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class TwitchChatApp(ctk.CTk):
    STREAM_HEIGHT = 300

    def __init__(self):
        super().__init__()
        self.title("TCR")
        self.geometry("560x720")
        self._normal_geom = "560x720"
        self._maximized = False
        self._drag_x = 0
        self._drag_y = 0
        self._grip_x = 0
        self._grip_y = 0
        self._grip_w = 0
        self._grip_h = 0
        self._resizing = False
        self._resize_after = None
        self._resize_w = 560
        self._resize_h = 720
        self.minsize(480, 640)
        self.overrideredirect(True)
        self.after(100, self._fix_taskbar_icon)

        # --- state, связанный с подключением (лениво) ---
        self.running = False
        self.stream_panel = None
        self.chat_client = None
        self.current_channel = ""

        # --- постоянно живущие объекты ---
        self._pinned = False
        self._spectrum_after = None
        self._bar_heights = []
        self.volume_var = ctk.DoubleVar(value=50)
        self.wishlist = load_wishlist()
        self.skin_assets = load_skin_assets(ACTIVE_SKIN)
        self._btn_images = []
        self._bg_label = None
        self._bg_path = None
        self._bg_raw = None
        self._bg_job = None
        self._bg_photo = None

        self._build_ui()
        self.after(150, self._set_window_icon)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self):
        s = load_skin()
        self.orange = s["orange"]
        self.orange2 = s["orange2"]
        self.amber = s["amber"]
        self.black = s["black"]
        self.dark = s["dark"]
        self.panel = s["panel"]
        self.panel2 = s["panel2"]
        self.line = s["line"]
        self.text_color = s["text"]
        self.muted = s["muted"]
        self.hover = s.get("hover", "#FFA733")
        self.button_hover = s.get("button_hover", "#333333")

        self.configure(fg_color=self.black)

        self._build_titlebar()

        # HEADER
        header_wrap = ctk.CTkFrame(self, fg_color=self.line, corner_radius=16)
        header_wrap.pack(fill="x", padx=14, pady=(14, 10))

        header = ctk.CTkFrame(header_wrap, fg_color=self.panel, corner_radius=14)
        header.pack(fill="both", expand=True, padx=2, pady=2)
        header.columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text=" LET’S WATCH ", text_color=self.orange2,
                     fg_color=self.panel, font=("Consolas", 15, "bold")).grid(
            row=0, column=0, padx=(12, 10), pady=8, sticky="w")

        self.status_var = ctk.StringVar(value="НЕ ПОДКЛЮЧЕНО")
        self.lcd_label = ctk.CTkLabel(header, textvariable=self.status_var,
                                      text_color=self.orange, fg_color=self.black,
                                      font=("Consolas", 12, "bold"), corner_radius=8)
        self.lcd_label.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        self.spectrum = tk.Canvas(header, width=170, height=26, bg=self.panel,
                                  bd=0, highlightthickness=0)
        self.spectrum.grid(row=0, column=2, padx=(10, 12), pady=8, sticky="e")
        self.after(250, self._animate_spectrum)

        # TOP
        top_wrap = ctk.CTkFrame(self, fg_color=self.black, corner_radius=16)
        top_wrap.pack(fill="x", padx=14, pady=(0, 10))

        top_frame = ctk.CTkFrame(top_wrap, fg_color=self.panel, corner_radius=14,
                                 border_width=2, border_color=self.orange)
        top_frame.pack(fill="both", expand=True, padx=0, pady=0)
        top_frame.columnconfigure(0, weight=1, minsize=90)

        self.channel_var = ctk.StringVar(value="")
        self.channel_entry = ctk.CTkEntry(
            top_frame, textvariable=self.channel_var,
            placeholder_text="Ссылка на канал или ник...",
            height=38, corner_radius=12,
            fg_color=self.black, text_color=self.text_color,
            border_color=self.orange, border_width=2, font=("Arial", 13)
        )
        self.channel_entry.grid(row=0, column=0, columnspan=3, sticky="ew",
                                padx=(12, 12), pady=(10, 4))
        self.channel_entry.bind("<Return>", lambda e: self.connect())

        self.connect_btn = ctk.CTkButton(
            top_frame, text="Подключиться", command=self.connect,
            fg_color=self.orange, hover_color=self.hover, text_color="#000000",
            height=38, width=130, corner_radius=12, font=("Arial", 12, "bold")
        )
        self.connect_btn.grid(row=1, column=0, sticky="w", padx=(12, 4), pady=(4, 10))

        dis_img = self._make_btn_image("button_disconnect", w=100, h=38)
        self.disconnect_btn = ctk.CTkButton(
            top_frame, text="Отключиться", command=self.disconnect, state="disabled",
            image=dis_img, compound="center" if dis_img else "left",
            fg_color=self.panel2 if not dis_img else "transparent",
            hover_color=self.button_hover if not dis_img else self.panel,
            text_color=self.text_color,
            height=38, width=100, corner_radius=12 if not dis_img else 0,
            font=("Arial", 12)
        )
        self.disconnect_btn.grid(row=1, column=1, sticky="w", padx=4, pady=(4, 10))

        ctrl = ctk.CTkFrame(top_frame, fg_color="transparent")
        ctrl.grid(row=1, column=2, sticky="e", padx=(4, 12), pady=(4, 10))

        self.add_wish_btn = ctk.CTkButton(
            ctrl, text="★", command=self.add_current_to_wishlist,
            fg_color=self.panel2, hover_color=self.button_hover, text_color=self.orange2,
            width=40, height=38, corner_radius=12, font=("Arial", 17, "bold")
        )
        self.add_wish_btn.pack(side="left", padx=(0, 4))

        self.pin_btn = ctk.CTkButton(
            ctrl, text="⇱", command=self.toggle_pin,
            fg_color=self.panel2, hover_color=self.button_hover, text_color=self.orange2,
            width=40, height=38, corner_radius=12, font=("Arial", 14)
        )
        self.pin_btn.pack(side="left", padx=4)

        self.volume_label = ctk.CTkLabel(ctrl, text="🔊", font=("Arial", 15),
                                         text_color=self.orange2, fg_color="transparent")
        self.volume_label.pack(side="left", padx=(8, 0))

        self.volume_slider = ctk.CTkSlider(
            ctrl, from_=0, to=100, variable=self.volume_var,
            progress_color=self.orange, button_color=self.orange2,
            button_hover_color=self.amber, width=90
        )
        self.volume_slider.pack(side="left", padx=(2, 0))

        # WISH
        wish_wrap = ctk.CTkFrame(self, fg_color=self.black, corner_radius=16)
        wish_wrap.pack(fill="x", padx=14, pady=(0, 10))

        wish_frame = ctk.CTkFrame(wish_wrap, fg_color=self.panel, corner_radius=14,
                                  border_width=2, border_color=self.orange)
        wish_frame.pack(fill="both", expand=True, padx=0, pady=0)
        wish_frame.columnconfigure(1, weight=1, minsize=110)

        ctk.CTkLabel(wish_frame, text="★ Wishlist каналов", text_color=self.orange2,
                     fg_color=self.panel, font=("Arial", 13, "bold")).grid(
            row=0, column=0, padx=(14, 8), pady=9, sticky="w")

        self.wish_menu = ctk.CTkOptionMenu(
            wish_frame, values=self.wishlist if self.wishlist else ["—"],
            command=self.on_wish_selected,
            fg_color=self.black, button_color=self.orange, button_hover_color=self.hover,
            text_color=self.text_color, dropdown_fg_color=self.panel,
            dropdown_text_color=self.text_color,
            dropdown_hover_color=shade(self.orange, 0.3),
            corner_radius=12, height=34
        )
        self.wish_menu.grid(row=0, column=1, padx=4, pady=9, sticky="ew")

        self.remove_wish_btn = ctk.CTkButton(
            wish_frame, text="Удалить", command=self.remove_selected_wish,
            fg_color=self.panel2, hover_color=self.button_hover, text_color=self.text_color,
            height=34, width=82, corner_radius=12
        )
        self.remove_wish_btn.grid(row=0, column=2, padx=(4, 12), pady=9)

        # STREAM SLOT
        self.stream_slot = tk.Frame(self, bg="#000000", bd=0, highlightthickness=0)
        self.stream_slot.pack(fill="x", side="top", padx=14, pady=(0, 10))
        self.stream_slot.pack_propagate(False)
        self.stream_slot.configure(height=0)

        # CHAT
        chat_wrap = ctk.CTkFrame(self, fg_color=self.black, corner_radius=16)
        chat_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        chat_frame = ctk.CTkFrame(chat_wrap, fg_color=self.dark, corner_radius=14,
                                  border_width=2, border_color=self.orange)
        chat_frame.pack(fill="both", expand=True, padx=0, pady=0)

        self.chat_log = ctk.CTkTextbox(
            chat_frame, wrap="word", fg_color="transparent",
            text_color=self.text_color, font=("Consolas", 14), corner_radius=12
        )
        self.chat_log.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat_log.tag_config("nick", foreground=self.orange2)
        self.chat_log.tag_config("system", foreground=self.muted)
        self.chat_log.configure(state="disabled")

    # =========================================================
    # assets / icon
    # =========================================================

    def _make_btn_image(self, *names, w=104, h=38):
        for name in names:
            p = self.skin_assets.get(name) or asset(name + ".png")
            if not p:
                continue
            try:
                img = Image.open(p).convert("RGBA").resize((w, h), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, size=(w, h))
                self._btn_images.append(ctk_img)
                return ctk_img
            except Exception:
                continue
        return None

    def _set_window_icon(self):
        p = self.skin_assets.get("icon") or asset("icon.png")
        if not p:
            return
        try:
            img = Image.open(p)
            self._icon_photo = ImageTk.PhotoImage(img)
            self.iconphoto(True, self._icon_photo)
        except Exception:
            pass

    def _fix_taskbar_icon(self):
        try:
            if os.name != "nt":
                return
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                return
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self.update_idletasks()
        except Exception:
            pass

    # =========================================================
    # titlebar / drag / resize
    # =========================================================

    def _build_titlebar(self):
        bar = ctk.CTkFrame(self, fg_color=self.panel, corner_radius=0,
                           border_width=0, height=56)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        title = ctk.CTkLabel(bar, text="  ♪ T C R ♪",
                             text_color=self.orange2,
                             font=("Consolas", 36, "bold"))
        title.pack(side="left", padx=(8, 0))

        for wdg in (bar, title):
            wdg.bind("<Button-1>", self._drag_start)
            wdg.bind("<B1-Motion>", self._drag_move)
            wdg.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.pack(side="right", padx=(0, 7))

        self.min_btn = ctk.CTkButton(
            btns, text="—", command=self._minimize,
            fg_color="transparent", hover_color=self.line, text_color=self.text_color,
            width=40, height=26, corner_radius=6, font=("Arial", 13, "bold"))
        self.min_btn.pack(side="left", padx=1)

        self.max_btn = ctk.CTkButton(
            btns, text="▢", command=self._toggle_maximize,
            fg_color="transparent", hover_color=self.line, text_color=self.text_color,
            width=40, height=26, corner_radius=6, font=("Arial", 13, "bold"))
        self.max_btn.pack(side="left", padx=1)

        self.close_btn = ctk.CTkButton(
            btns, text="✕", command=self.on_closing,
            fg_color="transparent", hover_color="#C0392B", text_color=self.text_color,
            width=44, height=26, corner_radius=6, font=("Arial", 12, "bold"))
        self.close_btn.pack(side="left", padx=1)

        sep = tk.Frame(self, bg=self.orange, height=2, bd=0, highlightthickness=0)
        sep.pack(fill="x", side="top")

        grip = tk.Canvas(self, width=18, height=18, bg=self.dark,
                         bd=0, highlightthickness=0, cursor="bottom_right_corner")
        grip.place(relx=1.0, rely=1.0, anchor="se", x=-3, y=-3)
        for i in range(4):
            off = 4 + i * 4
            grip.create_line(off, 17, 17, off, fill=self.orange, width=2)
        grip.bind("<Button-1>", self._grip_start)
        grip.bind("<B1-Motion>", self._grip_move)
        grip.bind("<ButtonRelease-1>", self._grip_end)

        self.bind("<Map>", self._on_mapped)

    def _drag_start(self, e):
        self._drag_x = e.x_root - self.winfo_rootx()
        self._drag_y = e.y_root - self.winfo_rooty()

    def _drag_move(self, e):
        if self._maximized:
            return
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _minimize(self):
        self.overrideredirect(False)
        self.iconify()

    def _on_mapped(self, e):
        if e.widget is self and not self._maximized:
            self.overrideredirect(True)
            self._fix_taskbar_icon()

    def _toggle_maximize(self):
        if self._maximized:
            self.geometry(self._normal_geom)
            self._maximized = False
            self.max_btn.configure(text="▢")
        else:
            self._normal_geom = self.geometry()
            w = self.winfo_screenwidth()
            h = self.winfo_screenheight()
            self.geometry(f"{w}x{h}+0+0")
            self._maximized = True
            self.max_btn.configure(text="▭")
        self.after_idle(self._finish_resize)

    def _grip_start(self, e):
        self._resizing = True
        self._grip_w = self.winfo_width()
        self._grip_h = self.winfo_height()
        self._grip_x = e.x_root
        self._grip_y = e.y_root
        self._resize_w = self._grip_w
        self._resize_h = self._grip_h
        if self._spectrum_after is not None:
            try:
                self.after_cancel(self._spectrum_after)
            except Exception:
                pass
            self._spectrum_after = None

    def _grip_move(self, e):
        if self._maximized:
            return
        self._resize_w = max(480, self._grip_w + (e.x_root - self._grip_x))
        self._resize_h = max(640, self._grip_h + (e.y_root - self._grip_y))
        if self._resize_after is None:
            self._resize_after = self.after(33, self._apply_resize)

    def _apply_resize(self):
        self._resize_after = None
        self.geometry(f"{self._resize_w}x{self._resize_h}")

    def _grip_end(self, e):
        if self._resize_after is not None:
            try:
                self.after_cancel(self._resize_after)
            except Exception:
                pass
            self._resize_after = None
            self._apply_resize()
        self._resizing = False
        self.after_idle(self._finish_resize)

    def _finish_resize(self):
        if self.stream_panel is not None:
            try:
                self.stream_panel.sync_now()
            except Exception:
                pass
        if self._spectrum_after is None and self.winfo_exists():
            self._animate_spectrum()

    # =========================================================
    # spectrum
    # =========================================================

    def _animate_spectrum(self):
        if not self.winfo_exists():
            return
        try:
            w = max(self.spectrum.winfo_width(), 60)
            h = max(self.spectrum.winfo_height(), 20)
        except Exception:
            return
        self.spectrum.delete("all")
        n = 14
        gap = 3
        bw = max(3, (w - (n - 1) * gap) // n)
        x = 2
        for i in range(n):
            if i >= len(self._bar_heights):
                self._bar_heights.append(random.randint(2, h))
            cur = self._bar_heights[i]
            target = random.randint(2, h)
            cur = int(cur + (target - cur) * 0.45)
            self._bar_heights[i] = cur
            bh = max(2, cur)
            color = (self.orange if bh > h * 0.6
                     else (shade(self.orange, 0.72) if bh > h * 0.3
                           else shade(self.orange, 0.38)))
            self.spectrum.create_rectangle(x, h - bh, x + bw, h, fill=color, outline="")
            x += bw + gap
        self._spectrum_after = self.after(130, self._animate_spectrum)

    # =========================================================
    # pin / wishlist
    # =========================================================

    def toggle_pin(self):
        self._pinned = not self._pinned
        self.attributes('-topmost', self._pinned)
        if self._pinned:
            self.pin_btn.configure(fg_color=self.orange, hover_color=self.hover,
                                   text_color="#000000")
        else:
            self.pin_btn.configure(fg_color=self.panel2, hover_color=self.button_hover,
                                   text_color=self.orange2)

    def refresh_wish_menu(self, selected=None):
        values = self.wishlist if self.wishlist else ["—"]
        self.wish_menu.configure(values=values)
        if selected in values:
            self.wish_menu.set(selected)
        elif values:
            self.wish_menu.set(values[0])

    def add_current_to_wishlist(self):
        channel = extract_channel_name(self.channel_var.get())
        if not channel:
            messagebox.showwarning("Канал не указан", "Введите ссылку или ник канала.")
            return
        if channel not in self.wishlist:
            self.wishlist.append(channel)
            save_wishlist(self.wishlist)
        self.refresh_wish_menu(selected=channel)
        self._append_system(f"★ Добавлено в wishlist: {channel}")

    def on_wish_selected(self, value):
        if value and value != "—":
            self.channel_var.set(value)
            self.connect()

    def remove_selected_wish(self):
        current = self.wish_menu.get()
        if current in self.wishlist:
            self.wishlist.remove(current)
            save_wishlist(self.wishlist)
            self.refresh_wish_menu()
            self._append_system(f"Удалено из wishlist: {current}")

    # =========================================================
    # connect / disconnect
    # =========================================================

    def connect(self):
        channel = extract_channel_name(self.channel_var.get())
        if not channel:
            messagebox.showwarning("Канал не указан",
                                   "Введите ссылку на канал Twitch или ник стримера.")
            return
        if self.running:
            return

        self.current_channel = channel
        self._stop_stream_panel()
        self.running = True
        self.connect_btn.configure(state="disabled", fg_color=self.panel2,
                                   text_color=self.text_color)
        self.disconnect_btn.configure(state="normal", fg_color=self.orange,
                                      text_color="#000000")
        self.channel_entry.configure(state="disabled")
        self.status_var.set(f"▶ #{channel.upper()}")
        self._append_system(f"--- Подключение к #{channel} ---")
        self.stream_slot.configure(height=self.STREAM_HEIGHT)

        # 1) стрим — лениво
        self.stream_panel = StreamPanel(self.stream_slot, channel, self.volume_var)

        # 2) чат — лениво
        self.chat_client = ChatClient(
            channel=channel,
            textbox=self.chat_log,
            on_system_msg=self._append_system,
        )
        self.chat_client.start()

    def _stop_stream_panel(self):
        if self.stream_panel:
            try:
                self.stream_panel.stop()
            except Exception:
                pass
            self.stream_panel = None
        try:
            self.stream_slot.configure(height=0)
        except Exception:
            pass

    def disconnect(self):
        if not self.running and not self.stream_panel and not self.chat_client:
            return
        self.running = False

        if self.chat_client is not None:
            try:
                self.chat_client.stop()
            except Exception:
                pass
            self.chat_client = None

        self._stop_stream_panel()
        self.status_var.set("ОТКЛЮЧЕНО")
        self._append_system("--- Отключено ---")
        self.connect_btn.configure(state="normal", fg_color=self.orange,
                                   text_color="#000000")
        self.disconnect_btn.configure(state="disabled", fg_color=self.panel2,
                                      text_color=self.text_color)
        self.channel_entry.configure(state="normal")

    # =========================================================
    # system messages
    # =========================================================

    def _append_system(self, text):
        try:
            self.after(0, self._do_append_system, text)
        except Exception:
            pass

    def _do_append_system(self, text):
        if not self.winfo_exists():
            return
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", f"{text}\n", "system")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    # =========================================================
    # closing
    # =========================================================

    def on_closing(self):
        if self._spectrum_after is not None:
            try:
                self.after_cancel(self._spectrum_after)
            except Exception:
                pass
            self._spectrum_after = None
        self.disconnect()
        self.destroy()


import updater # Импортируем наш новый файл

if __name__ == "__main__":
    app = TwitchChatApp()
    
    # Запускаем проверку обновлений в фоне, чтобы не подвешивать интерфейс
    import threading
    threading.Thread(target=updater.check_for_updates, args=(app,), daemon=True).start()
    
    app.mainloop()