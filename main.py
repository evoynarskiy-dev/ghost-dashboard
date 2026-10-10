import customtkinter as ctk
import tkinter as tk
import os
import glob
import json
import time
import threading
import subprocess
import calendar
import psutil
from datetime import datetime

THEME = {
    "bg": "#1e1e1e",
    "card": "#252526",
    "input": "#3c3c3c",
    "border": "#2d2d2d",
    "text": "#cccccc",
    "subtext": "#858585",
    "accent": "#007acc",
    "accent_hover": "#0e639c",
    "yellow": "#dcdcaa",
    "red": "#f44747",
    "red_hover": "#d13434",
    "btn": "#2d2d30",
    "btn_hover": "#37373d",
    "green": "#4ec9b0"
}

NOTES_FILE = os.path.expanduser("~/.config/ghost_notes.json")
MONTHS_RU_GEN = ["", "января", "февраля", "марта", "апреля", "мая", "июня", 
                 "июля", "августа", "сентября", "октября", "ноября", "декабря"]
MONTHS_RU_NOM = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
                 "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
DAYS_RU = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]

ctk.set_appearance_mode("dark")

class GhostDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Ghost Dashboard")
        self.geometry("520x1080")
        self.configure(fg_color=THEME["bg"])

        self.notes = self.load_notes()
        now = datetime.now()
        self.cur_year = now.year
        self.cur_month = now.month
        self.selected_date = now.strftime("%Y-%m-%d")
        self.last_stream_ids = []

        self.telemetry = {
            "cpu_pct": 0, "cpu_temp": "...", 
            "ram_used": 0, "ram_tot": 32, "ram_pct": 0,
            "gpu_util": 0, "gpu_temp": "...", "vram_used": 0, "vram_tot": 16,
            "net_down": "0 КБ/с", "net_up": "0 КБ/с", "net_ifaces": "..."
        }

        self.tabview = ctk.CTkTabview(
            self, 
            fg_color=THEME["bg"], 
            segmented_button_fg_color=THEME["card"],
            segmented_button_selected_color=THEME["accent"],
            segmented_button_selected_hover_color=THEME["accent_hover"],
            segmented_button_unselected_color=THEME["btn"],
            segmented_button_unselected_hover_color=THEME["btn_hover"],
            text_color=THEME["text"]
        )
        self.tabview.pack(fill="both", expand=True, padx=10, pady=5)

        self.tab_main = self.tabview.add("Главная")
        self.tab_perf = self.tabview.add("Железо")
        self.tab_audio = self.tabview.add("Звук")
        self.tab_proc = self.tabview.add("Процессы")

        self.setup_main_tab()
        self.setup_perf_tab()
        self.setup_audio_tab()
        self.setup_proc_tab()

        self.running = True
        self.bg_thread = threading.Thread(target=self.hardware_worker, daemon=True)
        self.bg_thread.start()

        self.tick()
        self.gui_telemetry_loop()
        self.update_audio_sync()
        self.auto_refresh_streams_loop()

    # ==========================================
    #       ФОНОВАЯ ТЕЛЕМЕТРИЯ (БЕЗ ЛАГОВ)
    # ==========================================
    def hardware_worker(self):
        last_t = time.time()
        last_io = psutil.net_io_counters()

        while self.running:
            try:
                c_pct = psutil.cpu_percent(interval=None)
                c_temp = "Н/Д"
                try:
                    temps = psutil.sensors_temperatures()
                    if 'k10temp' in temps:
                        for t in temps['k10temp']:
                            if t.label in ('Tctl', 'Tdie'):
                                c_temp = f"{t.current:.0f}°C"
                                break
                        if c_temp == "Н/Д" and temps['k10temp']:
                            c_temp = f"{temps['k10temp'][0].current:.0f}°C"
                except:
                    pass

                mem = psutil.virtual_memory()
                r_used = mem.used / (1024**3)
                r_tot = mem.total / (1024**3)

                g_util, g_temp, v_used, v_tot = 0, "...", 0, 16
                try:
                    out = subprocess.check_output(
                        ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                        text=True, timeout=0.8
                    ).strip()
                    gu, gt, vu, vt = out.split(", ")
                    g_util = float(gu)
                    g_temp = f"{gt}°C"
                    v_used = int(vu) / 1024
                    v_tot = int(vt) / 1024
                except:
                    pass

                now_t = time.time()
                dt = now_t - last_t
                n_down, n_up = "0 КБ/с", "0 КБ/с"
                if dt > 0:
                    cur_io = psutil.net_io_counters()
                    d_spd = (cur_io.bytes_recv - last_io.bytes_recv) / dt
                    u_spd = (cur_io.bytes_sent - last_io.bytes_sent) / dt
                    def fmt(b):
                        return f"{b / (1024**2):.1f} МБ/с" if b >= 1024**2 else f"{b / 1024:.0f} КБ/с"
                    n_down = fmt(d_spd)
                    n_up = fmt(u_spd)
                    last_io = cur_io
                    last_t = now_t

                stats = psutil.net_if_stats()
                active = [i for i, st in stats.items() if st.isup and i != "lo"]

                self.telemetry = {
                    "cpu_pct": c_pct, "cpu_temp": c_temp,
                    "ram_used": r_used, "ram_tot": r_tot, "ram_pct": mem.percent,
                    "gpu_util": g_util, "gpu_temp": g_temp, "vram_used": v_used, "vram_tot": v_tot,
                    "net_down": n_down, "net_up": n_up, "net_ifaces": ", ".join(active[:4])
                }
            except Exception:
                pass
            time.sleep(1.0)

    def gui_telemetry_loop(self):
        t = self.telemetry
        self.cpu_label.configure(text=f"Загрузка: {t['cpu_pct']:.1f}% | Температура: {t['cpu_temp']}")
        self.cpu_bar.set(t['cpu_pct'] / 100.0)

        self.ram_label.configure(text=f"Использовано: {t['ram_used']:.1f} ГБ / {t['ram_tot']:.1f} ГБ ({t['ram_pct']}%)")
        self.ram_bar.set(t['ram_pct'] / 100.0)

        self.gpu_label.configure(text=f"Утилизация: {t['gpu_util']:.0f}% | Температура: {t['gpu_temp']}")
        self.gpu_vram_label.configure(text=f"Видеопамять: {t['vram_used']:.2f} ГБ / {t['vram_tot']:.2f} ГБ")
        self.gpu_bar.set(t['gpu_util'] / 100.0)

        self.net_speed_label.configure(text=f"↓ {t['net_down']}  |  ↑ {t['net_up']}")
        self.net_dev_label.configure(text="Адаптеры: " + t['net_ifaces'])

        self.after(500, self.gui_telemetry_loop)

    # ==========================================
    #               ВКЛАДКА: ГЛАВНАЯ
    # ==========================================
    def setup_main_tab(self):
        self.anim_canvas = tk.Canvas(self.tab_main, height=36, bg=THEME["bg"], highlightthickness=0)
        self.anim_canvas.pack(fill="x", padx=10, pady=(4, 0))
        self.pac_x = 0
        self.pac_mouth = 35
        self.pac_mouth_closing = True
        self.animate_chase()

        self.time_label = ctk.CTkLabel(self.tab_main, text="", font=("JetBrains Mono", 36, "bold"), text_color="#ffffff")
        self.time_label.pack(pady=(0, 0))
        self.date_label = ctk.CTkLabel(self.tab_main, text="", font=("JetBrains Mono", 13), text_color=THEME["subtext"])
        self.date_label.pack(pady=(0, 4))

        self.cal_frame = ctk.CTkFrame(self.tab_main, fg_color=THEME["card"], corner_radius=6)
        self.cal_frame.pack(fill="x", padx=10, pady=3)

        nav_frame = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkButton(nav_frame, text="<", width=26, height=22, fg_color=THEME["btn"], hover_color=THEME["btn_hover"], 
                      text_color=THEME["text"], command=self.prev_month).pack(side="left")
        self.month_label = ctk.CTkLabel(nav_frame, text="", font=("JetBrains Mono", 13, "bold"), text_color=THEME["text"])
        self.month_label.pack(side="left", padx=8)
        ctk.CTkButton(nav_frame, text="Сегодня", width=60, height=22, fg_color=THEME["btn"], hover_color=THEME["accent"], 
                      text_color=THEME["text"], font=("JetBrains Mono", 11), command=self.go_today).pack(side="left", padx=5)
        ctk.CTkButton(nav_frame, text=">", width=26, height=22, fg_color=THEME["btn"], hover_color=THEME["btn_hover"], 
                      text_color=THEME["text"], command=self.next_month).pack(side="right")

        self.grid_frame = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        self.grid_frame.pack(padx=10, pady=2)
        self.render_calendar()

        # Заметки
        self.note_frame = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        self.note_frame.pack(fill="x", padx=10, pady=(4, 6))
        self.note_entry = ctk.CTkEntry(self.note_frame, placeholder_text="Напоминалка...", fg_color=THEME["input"],
                                        border_color=THEME["border"], height=26, font=("JetBrains Mono", 11))
        self.note_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.note_entry.bind("<Return>", lambda e: self.add_note())

        ctk.CTkButton(self.note_frame, text="+", width=26, height=26, fg_color=THEME["accent"], 
                      hover_color=THEME["accent_hover"], text_color="#ffffff", command=self.add_note).pack(side="left", padx=2)
        ctk.CTkButton(self.note_frame, text="✕", width=26, height=26, fg_color=THEME["red"], 
                      hover_color=THEME["red_hover"], text_color="#ffffff", command=self.delete_note).pack(side="left", padx=2)

        self.note_display = ctk.CTkLabel(self.cal_frame, text="", font=("JetBrains Mono", 11), text_color=THEME["yellow"], wraplength=450)
        self.note_display.pack(padx=10, pady=(0, 6))
        self.update_note_display()

        # War Thunder
        wt_frame = ctk.CTkFrame(self.tab_main, fg_color=THEME["card"], corner_radius=6)
        wt_frame.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(wt_frame, text="WAR THUNDER", font=("JetBrains Mono", 12, "bold"), text_color=THEME["accent"]).pack(side="left", padx=10)
        ctk.CTkButton(wt_frame, text="Запуск", width=70, height=26, fg_color=THEME["btn"], hover_color=THEME["accent"], 
                      font=("JetBrains Mono", 11), command=self.launch_warthunder).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(wt_frame, text="KILL", width=70, height=26, fg_color=THEME["red"], hover_color=THEME["red_hover"], 
                      font=("JetBrains Mono", 11, "bold"), command=self.kill_warthunder).pack(side="right", padx=10, pady=5)

        # Быстрый звук
        vol_quick = ctk.CTkFrame(self.tab_main, fg_color=THEME["card"], corner_radius=6)
        vol_quick.pack(fill="x", padx=10, pady=3)
        self.quick_vol_btn = ctk.CTkButton(vol_quick, text="VOL", width=44, height=26, fg_color=THEME["btn"], hover_color=THEME["accent"], 
                                           command=lambda: self.toggle_mute("@DEFAULT_AUDIO_SINK@"))
        self.quick_vol_btn.pack(side="left", padx=8, pady=4)
        self.quick_vol_slider = ctk.CTkSlider(vol_quick, from_=0, to=100, number_of_steps=100, fg_color=THEME["input"], 
                                              progress_color=THEME["accent"], command=lambda v: self.set_volume_fast(v, "@DEFAULT_AUDIO_SINK@"))
        self.quick_vol_slider.pack(side="left", fill="x", expand=True, padx=8)
        self.quick_vol_lbl = ctk.CTkLabel(vol_quick, text="..%", font=("JetBrains Mono", 11), width=42)
        self.quick_vol_lbl.pack(side="right", padx=8)

        # Программы
        self.search_entry = ctk.CTkEntry(self.tab_main, placeholder_text="Поиск программ...", fg_color=THEME["input"],
                                         border_color=THEME["border"], height=28, font=("JetBrains Mono", 12))
        self.search_entry.pack(fill="x", padx=10, pady=(5, 3))
        self.search_entry.bind("<KeyRelease>", self.filter_apps)

        self.app_scroll = ctk.CTkScrollableFrame(self.tab_main, fg_color=THEME["card"], corner_radius=6, height=200)
        self.app_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        self.all_apps = self.scan_installed_apps()
        self.render_apps(self.all_apps)

    def launch_warthunder(self):
        subprocess.Popen("cd ~/Games/WarThunder && ./launcher", shell=True)

    def kill_warthunder(self):
        subprocess.Popen("killall -9 aces.x86_64 || killall -9 aces || pkill -9 -f warthunder", shell=True)

    # ==========================================
    #      ВКЛАДКА: ЗВУК (АВТО-МИКШЕР)
    # ==========================================
    def setup_audio_tab(self):
        master_box = ctk.CTkFrame(self.tab_audio, fg_color=THEME["card"], corner_radius=6)
        master_box.pack(fill="x", padx=10, pady=6)
        
        row1 = ctk.CTkFrame(master_box, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(8, 2))
        self.audio_sink_lbl = ctk.CTkLabel(row1, text="ОСНОВНАЯ ГРОМКОСТЬ: 0%", font=("JetBrains Mono", 13, "bold"), text_color=THEME["accent"])
        self.audio_sink_lbl.pack(side="left")
        self.mute_sink_btn = ctk.CTkButton(row1, text="Mute", width=65, height=24, fg_color=THEME["btn"], hover_color=THEME["red"], 
                                           command=lambda: self.toggle_mute("@DEFAULT_AUDIO_SINK@"))
        self.mute_sink_btn.pack(side="right")

        self.sink_slider = ctk.CTkSlider(master_box, from_=0, to=100, number_of_steps=100, fg_color=THEME["input"], 
                                         progress_color=THEME["accent"], command=lambda v: self.set_volume_fast(v, "@DEFAULT_AUDIO_SINK@"))
        self.sink_slider.pack(fill="x", padx=12, pady=(4, 8))

        mixer_header = ctk.CTkFrame(self.tab_audio, fg_color="transparent")
        mixer_header.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(mixer_header, text="МИКШЕР ПРИЛОЖЕНИЙ (АВТО-ОБНОВЛЕНИЕ)", font=("JetBrains Mono", 12, "bold"), text_color=THEME["green"]).pack(side="left")

        self.mixer_scroll = ctk.CTkScrollableFrame(self.tab_audio, fg_color=THEME["card"], corner_radius=6, height=520)
        self.mixer_scroll.pack(fill="both", expand=True, padx=10, pady=5)

        self.refresh_app_streams()

    def get_sink_inputs(self):
        env = dict(os.environ, LC_ALL="C")
        try:
            out = subprocess.check_output(["pactl", "-f", "json", "list", "sink-inputs"], env=env, text=True, errors="ignore")
            data = json.loads(out)
            res = []
            for item in data:
                s_id = str(item.get("index", ""))
                props = item.get("properties", {})
                name = props.get("application.name") or props.get("media.name") or props.get("node.name") or "Аудиопоток"
                vols = item.get("volume", {})
                vol = 100
                for ch, val in vols.items():
                    if isinstance(val, dict) and "value_percent" in val:
                        vol = int(val["value_percent"].replace("%", ""))
                        break
                muted = bool(item.get("mute", False))
                res.append({"id": s_id, "name": name, "vol": vol, "muted": muted})
            if res:
                return res
        except:
            pass

        try:
            out = subprocess.check_output(["pactl", "list", "sink-inputs"], env=env, text=True, errors="ignore")
            streams = []
            curr = None
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Sink Input #"):
                    if curr:
                        streams.append(curr)
                    curr = {"id": line.split("#")[1].strip(), "name": "Неизвестно", "vol": 100, "muted": False}
                elif curr:
                    if "application.name =" in line:
                        curr["name"] = line.split("=", 1)[1].strip().strip('"')
                    elif "media.name =" in line and curr["name"] == "Неизвестно":
                        curr["name"] = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("Mute:"):
                        curr["muted"] = ("yes" in line.lower())
                    elif "Volume:" in line and "%" in line:
                        for token in line.split("/"):
                            if "%" in token:
                                try:
                                    curr["vol"] = int(token.replace("%", "").strip())
                                    break
                                except:
                                    pass
            if curr:
                streams.append(curr)
            return streams
        except:
            return []

    # Умный автоопрос раз в 1.5 секунды (без мерцания интерфейса)
    def auto_refresh_streams_loop(self):
        streams = self.get_sink_inputs()
        current_ids = [st["id"] for st in streams]
        if current_ids != self.last_stream_ids:
            self.refresh_app_streams(streams)
            self.last_stream_ids = current_ids

        self.after(1500, self.auto_refresh_streams_loop)

    def refresh_app_streams(self, streams=None):
        if streams is None:
            streams = self.get_sink_inputs()
            self.last_stream_ids = [st["id"] for st in streams]

        for w in self.mixer_scroll.winfo_children():
            w.destroy()

        if not streams:
            ctk.CTkLabel(self.mixer_scroll, text="Нет активных звуковых потоков.\nВключи видео в Chrome или игру!", 
                         font=("JetBrains Mono", 12), text_color=THEME["subtext"]).pack(pady=40)
            return

        for st in streams:
            box = ctk.CTkFrame(self.mixer_scroll, fg_color=THEME["btn"], corner_radius=6)
            box.pack(fill="x", pady=4, padx=4)

            top_row = ctk.CTkFrame(box, fg_color="transparent")
            top_row.pack(fill="x", padx=8, pady=(6, 2))

            ctk.CTkLabel(top_row, text=f"{st['name']}", font=("JetBrains Mono", 12, "bold"), text_color=THEME["text"]).pack(side="left")

            vol_val_lbl = ctk.CTkLabel(top_row, text=f"{st['vol']}%", font=("JetBrains Mono", 11), text_color=THEME["subtext"])
            vol_val_lbl.pack(side="left", padx=10)

            mute_btn = ctk.CTkButton(
                top_row, 
                text="Mute" if not st["muted"] else "Unmute", 
                width=65, 
                height=22, 
                fg_color=THEME["red"] if st["muted"] else THEME["input"],
                hover_color=THEME["red_hover"],
                font=("JetBrains Mono", 10),
                command=lambda s_id=st["id"]: self.toggle_stream_mute(s_id)
            )
            mute_btn.pack(side="right")

            slider = ctk.CTkSlider(
                box, 
                from_=0, 
                to=100, 
                number_of_steps=100, 
                fg_color=THEME["input"], 
                progress_color=THEME["accent"],
                command=lambda val, s_id=st["id"], lbl=vol_val_lbl: self.set_stream_vol_fast(s_id, val, lbl)
            )
            slider.set(st["vol"])
            slider.pack(fill="x", padx=8, pady=(2, 8))

    def set_stream_vol_fast(self, stream_id, val, lbl):
        v = int(val)
        lbl.configure(text=f"{v}%")
        subprocess.Popen(["pactl", "set-sink-input-volume", str(stream_id), f"{v}%"])

    def toggle_stream_mute(self, stream_id):
        subprocess.Popen(["pactl", "set-sink-input-mute", str(stream_id), "toggle"])
        self.after(150, lambda: self.refresh_app_streams())

    def set_volume_fast(self, val, target):
        v_int = int(val)
        if target == "@DEFAULT_AUDIO_SINK@":
            if hasattr(self, 'audio_sink_lbl'):
                self.audio_sink_lbl.configure(text=f"ОСНОВНАЯ ГРОМКОСТЬ: {v_int}%")
            if hasattr(self, 'quick_vol_lbl'):
                self.quick_vol_lbl.configure(text=f"{v_int}%")
        v_float = v_int / 100.0
        subprocess.Popen(["wpctl", "set-volume", "-l", "1.5", target, f"{v_float:.2f}"])

    def toggle_mute(self, target):
        subprocess.Popen(["wpctl", "set-mute", target, "toggle"])
        self.after(100, self.update_audio_sync)

    def update_audio_sync(self):
        try:
            out = subprocess.check_output(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], text=True).strip()
            parts = out.split()
            sink_v = int(float(parts[1]) * 100)
            sink_m = "[MUTED]" in out

            if hasattr(self, 'audio_sink_lbl'):
                self.audio_sink_lbl.configure(text=f"ОСНОВНАЯ ГРОМКОСТЬ: {sink_v}% {'[ВЫКЛ]' if sink_m else ''}")
                self.sink_slider.set(sink_v)
                self.mute_sink_btn.configure(text="Unmute" if sink_m else "Mute", fg_color=THEME["red"] if sink_m else THEME["btn"])

            if hasattr(self, 'quick_vol_slider'):
                self.quick_vol_slider.set(sink_v)
                self.quick_vol_lbl.configure(text=f"{sink_v}%")
                self.quick_vol_btn.configure(text="MUTE" if sink_m else "VOL", fg_color=THEME["red"] if sink_m else THEME["btn"])
        except:
            pass

        self.after(3000, self.update_audio_sync)

    # ==========================================
    #               ВКЛАДКА: ЖЕЛЕЗО
    # ==========================================
    def setup_perf_tab(self):
        cpu_box = ctk.CTkFrame(self.tab_perf, fg_color=THEME["card"], corner_radius=6)
        cpu_box.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(cpu_box, text="AMD Ryzen 7 7800X3D", font=("JetBrains Mono", 14, "bold"), text_color=THEME["accent"]).pack(anchor="w", padx=12, pady=(8, 2))
        self.cpu_label = ctk.CTkLabel(cpu_box, text="Загрузка: ... | Температура: ...", font=("JetBrains Mono", 13), text_color=THEME["text"])
        self.cpu_label.pack(anchor="w", padx=12)
        self.cpu_bar = ctk.CTkProgressBar(cpu_box, fg_color=THEME["input"], progress_color=THEME["accent"])
        self.cpu_bar.pack(fill="x", padx=12, pady=(5, 10))

        ram_box = ctk.CTkFrame(self.tab_perf, fg_color=THEME["card"], corner_radius=6)
        ram_box.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(ram_box, text="Оперативная память (DDR5)", font=("JetBrains Mono", 14, "bold"), text_color=THEME["accent"]).pack(anchor="w", padx=12, pady=(8, 2))
        self.ram_label = ctk.CTkLabel(ram_box, text="Память: ...", font=("JetBrains Mono", 13), text_color=THEME["text"])
        self.ram_label.pack(anchor="w", padx=12)
        self.ram_bar = ctk.CTkProgressBar(ram_box, fg_color=THEME["input"], progress_color=THEME["accent"])
        self.ram_bar.pack(fill="x", padx=12, pady=(5, 10))

        gpu_box = ctk.CTkFrame(self.tab_perf, fg_color=THEME["card"], corner_radius=6)
        gpu_box.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(gpu_box, text="NVIDIA GeForce RTX 5060 Ti", font=("JetBrains Mono", 14, "bold"), text_color="#76b900").pack(anchor="w", padx=12, pady=(8, 2))
        self.gpu_label = ctk.CTkLabel(gpu_box, text="Утилизация: ... | Температура: ...", font=("JetBrains Mono", 13), text_color=THEME["text"])
        self.gpu_label.pack(anchor="w", padx=12)
        self.gpu_vram_label = ctk.CTkLabel(gpu_box, text="VRAM: ...", font=("JetBrains Mono", 12), text_color=THEME["subtext"])
        self.gpu_vram_label.pack(anchor="w", padx=12)
        self.gpu_bar = ctk.CTkProgressBar(gpu_box, fg_color=THEME["input"], progress_color="#76b900")
        self.gpu_bar.pack(fill="x", padx=12, pady=(5, 10))

        net_box = ctk.CTkFrame(self.tab_perf, fg_color=THEME["card"], corner_radius=6)
        net_box.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(net_box, text="Сетевые адаптеры и Трафик", font=("JetBrains Mono", 14, "bold"), text_color=THEME["green"]).pack(anchor="w", padx=12, pady=(8, 2))
        self.net_speed_label = ctk.CTkLabel(net_box, text="↓ 0 КБ/с  |  ↑ 0 КБ/с", font=("JetBrains Mono", 13, "bold"), text_color=THEME["text"])
        self.net_speed_label.pack(anchor="w", padx=12)
        self.net_dev_label = ctk.CTkLabel(net_box, text="Адаптеры: ...", font=("JetBrains Mono", 11), text_color=THEME["subtext"], justify="left")
        self.net_dev_label.pack(anchor="w", padx=12, pady=(2, 10))

    # ==========================================
    #               ВКЛАДКА: ПРОЦЕССЫ
    # ==========================================
    def setup_proc_tab(self):
        top_bar = ctk.CTkFrame(self.tab_proc, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(6, 4))
        ctk.CTkLabel(top_bar, text="АКТИВНЫЕ ПРИЛОЖЕНИЯ", font=("JetBrains Mono", 13, "bold"), text_color=THEME["accent"]).pack(side="left")
        ctk.CTkButton(top_bar, text="Обновить", width=80, height=26, fg_color=THEME["btn"], hover_color=THEME["btn_hover"], 
                      command=self.refresh_proc_list).pack(side="right")

        self.proc_scroll = ctk.CTkScrollableFrame(self.tab_proc, fg_color=THEME["card"], corner_radius=6, height=800)
        self.proc_scroll.pack(fill="both", expand=True, padx=10, pady=5)
        self.refresh_proc_list()

    def refresh_proc_list(self):
        for w in self.proc_scroll.winfo_children():
            w.destroy()

        user_apps = ["kitty", "alacritty", "telegram-desktop", "code", "steam", "discord", 
                     "yandex-music", "happ", "pavucontrol", "thunar", "aces.x86_64", "launcher", "chrome", "firefox"]

        found = []
        for p in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                name = p.info['name'].lower()
                if any(app in name for app in user_apps):
                    mem_mb = p.info['memory_info'].rss / (1024 * 1024)
                    found.append((p.info['name'], p.info['pid'], mem_mb))
            except:
                continue

        for name, pid, mem_mb in sorted(found, key=lambda x: x[2], reverse=True):
            row = ctk.CTkFrame(self.proc_scroll, fg_color=THEME["btn"], corner_radius=4)
            row.pack(fill="x", pady=2, padx=4)

            ctk.CTkLabel(row, text=f"{name} ({pid})", font=("JetBrains Mono", 12), text_color=THEME["text"]).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=f"{mem_mb:.0f} МБ", font=("JetBrains Mono", 11), text_color=THEME["subtext"]).pack(side="left", padx=8)

            ctk.CTkButton(
                row, 
                text="Убить", 
                width=60, 
                height=22, 
                fg_color=THEME["red"], 
                hover_color=THEME["red_hover"],
                font=("JetBrains Mono", 11, "bold"),
                command=lambda p_id=pid: self.kill_pid(p_id)
            ).pack(side="right", padx=6, pady=4)

    def kill_pid(self, pid):
        try:
            os.kill(pid, 9)
        except:
            pass
        self.after(200, self.refresh_proc_list)

    # --- АНИМАЦИЯ CANVAS ---
    def animate_chase(self):
        self.anim_canvas.delete("all")
        w = self.anim_canvas.winfo_width()
        if w < 100:
            w = 480

        gx = (self.pac_x + 60) % (w + 80) - 20
        px = self.pac_x % (w + 80) - 20
        y = 18
        r = 13

        self.anim_canvas.create_arc(gx-r, y-r, gx+r, y+r, start=0, extent=180, fill="#4ec9b0", outline="")
        self.anim_canvas.create_rectangle(gx-r, y, gx+r, y+r-4, fill="#4ec9b0", outline="")
        self.anim_canvas.create_polygon(
            gx-r, y+r-4, gx-r+4, y+r, gx-r+8, y+r-4, 
            gx, y+r, gx+r-8, y+r-4, gx+r-4, y+r, gx+r, y+r-4, 
            fill="#4ec9b0"
        )
        self.anim_canvas.create_oval(gx-6, y-5, gx-2, y-1, fill="#ffffff", outline="")
        self.anim_canvas.create_oval(gx+2, y-5, gx+6, y-1, fill="#ffffff", outline="")
        self.anim_canvas.create_oval(gx-4, y-4, gx-2, y-2, fill="#007acc", outline="")
        self.anim_canvas.create_oval(gx+4, y-4, gx+6, y-2, fill="#007acc", outline="")

        m = self.pac_mouth
        self.anim_canvas.create_arc(px-r, y-r, px+r, y+r, start=m, extent=360-(2*m), fill="#ffcc00", outline="")
        self.anim_canvas.create_oval(px, y-8, px+3, y-5, fill="#1e1e1e", outline="")

        self.pac_x += 3
        if self.pac_mouth_closing:
            self.pac_mouth -= 5
            if self.pac_mouth <= 5:
                self.pac_mouth_closing = False
        else:
            self.pac_mouth += 5
            if self.pac_mouth >= 35:
                self.pac_mouth_closing = True

        self.after(25, self.animate_chase)

    # --- ТАЙМЕРЫ И КАЛЕНДАРЬ ---
    def tick(self):
        now = datetime.now()
        self.time_label.configure(text=now.strftime("%H:%M:%S"))
        day_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][now.weekday()]
        self.date_label.configure(text=f"{day_ru}, {now.day} {MONTHS_RU_GEN[now.month]} {now.year}")
        self.after(1000, self.tick)

    def render_calendar(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        self.month_label.configure(text=f"{MONTHS_RU_NOM[self.cur_month]} {self.cur_year}")

        for col, day_name in enumerate(DAYS_RU):
            color = THEME["accent"] if col == 0 else THEME["subtext"]
            ctk.CTkLabel(self.grid_frame, text=day_name, width=38, font=("JetBrains Mono", 11, "bold"), 
                         text_color=color).grid(row=0, column=col, padx=1, pady=1)

        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(self.cur_year, self.cur_month)
        today_str = datetime.now().strftime("%Y-%m-%d")

        for r, week in enumerate(month_days):
            for c, day in enumerate(week):
                if day == 0:
                    continue
                date_key = f"{self.cur_year}-{self.cur_month:02d}-{day:02d}"
                has_notes = date_key in self.notes and len(self.notes[date_key]) > 0
                is_today = (date_key == today_str)
                is_selected = (date_key == self.selected_date)

                fg = THEME["btn"]
                if is_today:
                    fg = "#3e3e42"
                if is_selected:
                    fg = THEME["accent"]

                txt_color = THEME["text"]
                if is_selected:
                    txt_color = "#ffffff"
                elif has_notes:
                    txt_color = THEME["yellow"]

                btn = ctk.CTkButton(
                    self.grid_frame, 
                    text=f"{day}{'•' if has_notes else ''}", 
                    width=38, 
                    height=24, 
                    fg_color=fg,
                    hover_color=THEME["accent_hover"],
                    text_color=txt_color,
                    font=("JetBrains Mono", 10, "bold" if is_today or has_notes else "normal"),
                    command=lambda d=date_key: self.select_date(d)
                )
                btn.grid(row=r+1, column=c, padx=1, pady=1)

    def select_date(self, date_key):
        self.selected_date = date_key
        self.render_calendar()
        self.update_note_display()

    def go_today(self):
        now = datetime.now()
        self.cur_year = now.year
        self.cur_month = now.month
        self.selected_date = now.strftime("%Y-%m-%d")
        self.render_calendar()
        self.update_note_display()

    def prev_month(self):
        self.cur_month -= 1
        if self.cur_month < 1:
            self.cur_month = 12
            self.cur_year -= 1
        self.render_calendar()

    def next_month(self):
        self.cur_month += 1
        if self.cur_month > 12:
            self.cur_month = 1
            self.cur_year += 1
        self.render_calendar()

    def load_notes(self):
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_notes(self):
        os.makedirs(os.path.dirname(NOTES_FILE), exist_ok=True)
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(self.notes, f, ensure_ascii=False, indent=2)

    def add_note(self):
        text = self.note_entry.get().strip()
        if text:
            if self.selected_date not in self.notes:
                self.notes[self.selected_date] = []
            self.notes[self.selected_date].append(text)
            self.save_notes()
            self.note_entry.delete(0, "end")
            self.render_calendar()
            self.update_note_display()

    def delete_note(self):
        if self.selected_date in self.notes:
            del self.notes[self.selected_date]
            self.save_notes()
            self.render_calendar()
            self.update_note_display()

    def update_note_display(self):
        items = self.notes.get(self.selected_date, [])
        if items:
            self.note_display.configure(text=f"[{self.selected_date}]:\n" + "\n".join([f"• {x}" for x in items]))
        else:
            self.note_display.configure(text=f"[{self.selected_date}]: Нет заметок")

    def scan_installed_apps(self):
        apps = []
        paths = ["/usr/share/applications/*.desktop", os.path.expanduser("~/.local/share/applications/*.desktop")]
        seen = set()
        ignore_keywords = ["avahi", "cmake", "bssh", "bvnc", "qv4l2", "qvidcap", "$game_name"]

        for p in paths:
            for filepath in glob.glob(p):
                try:
                    name, exec_cmd, nodisplay = None, None, False
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if line.startswith("Name=") and not name:
                                name = line.split("=", 1)[1].strip()
                            elif line.startswith("Exec=") and not exec_cmd:
                                exec_cmd = line.split("=", 1)[1].strip().split("%")[0].strip()
                            elif line.startswith("NoDisplay=true"):
                                nodisplay = True
                    if name and exec_cmd and not nodisplay and name not in seen:
                        if any(ign in name.lower() or ign in exec_cmd.lower() for ign in ignore_keywords):
                            continue
                        seen.add(name)
                        apps.append((name, exec_cmd))
                except:
                    continue

        return sorted(apps, key=lambda x: x[0].lower())

    def render_apps(self, app_list):
        for widget in self.app_scroll.winfo_children():
            widget.destroy()

        for name, cmd in app_list:
            btn = ctk.CTkButton(
                self.app_scroll,
                text=name,
                anchor="w",
                fg_color=THEME["btn"],
                hover_color=THEME["btn_hover"],
                text_color=THEME["text"],
                font=("JetBrains Mono", 12),
                height=30,
                corner_radius=4,
                command=lambda c=cmd: subprocess.Popen(c, shell=True)
            )
            btn.pack(fill="x", pady=2)

    def filter_apps(self, event=None):
        query = self.search_entry.get().lower().strip()
        if not query:
            self.render_apps(self.all_apps)
        else:
            filtered = [app for app in self.all_apps if query in app[0].lower()]
            self.render_apps(filtered)

if __name__ == "__main__":
    app = GhostDashboard()
    app.mainloop()
