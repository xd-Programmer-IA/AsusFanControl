#!/usr/bin/env python3
"""ASUS Fan Control v2 - Advanced fan management for ASUS laptops"""

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont
import ctypes
import json
import os
import sys
import threading
import time
import math
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

APP_NAME    = "ASUS Fan Control"
APP_VERSION = "2.0.0"
SETTINGS_DIR  = Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "AsusFanControl"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

TEMP_NORMAL_DEFAULT = 55   # °C: below → Normal
TEMP_MEDIUM_DEFAULT = 70   # °C: below → Equilibrado, above → Rápido

DUTY_NORMAL_DEFAULT = 35
DUTY_MEDIUM_DEFAULT = 50   # 50% for Equilibrado
DUTY_FAST_DEFAULT   = 100

MONITOR_INTERVAL = 8    # seconds between auto-mode temp checks
STATS_INTERVAL   = 4000  # ms between UI stats refresh

LOG_FILE = Path("C:/ProgramData/AsusFanControl/debug.log")

def _log(msg: str):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

# ── Colors ────────────────────────────────────────────────────────────────────

C_BG     = "#0d0d0d"
C_CARD   = "#1a1a1a"
C_BORDER = "#2e2e2e"
C_ACCENT = "#0070d2"
C_NORMAL = "#22c55e"
C_MEDIUM = "#f97316"
C_FAST   = "#ef4444"
C_AUTO   = "#3b82f6"
C_TEXT   = "#f0f0f0"
C_MUTED  = "#7a7a7a"
C_WHITE  = "#ffffff"


# ── DLL Interface ─────────────────────────────────────────────────────────────

class AsusWinIO:
    def __init__(self, dll_path: str):
        self._dll       = None
        self._dll_path  = dll_path
        self._ready     = False
        self._fan_count = 0

    def initialize(self) -> bool:
        try:
            ctypes.windll.ole32.CoInitializeEx(None, 0)
            _log("CoInitializeEx done")
            self._dll = ctypes.CDLL(self._dll_path)
            self._bind_signatures()
            r1 = bool(self._dll.InitializeWinIo())
            _log(f"InitializeWinIo -> {r1}")
            r2 = False
            try:
                self._dll.InitializeATKACPIDevice.restype  = ctypes.c_bool
                self._dll.InitializeATKACPIDevice.argtypes = []
                r2 = bool(self._dll.InitializeATKACPIDevice())
                _log(f"InitializeATKACPIDevice -> {r2}")
            except Exception as e:
                _log(f"InitializeATKACPIDevice not found: {e}")
            self._ready = r1 or r2
            if self._ready:
                self._probe_dll()
            return self._ready
        except Exception as e:
            _log(f"init error: {e}")
            return False

    def _bind_signatures(self):
        d = self._dll
        # Signatures confirmed from reference app C# assembly (AsusSystemAnalysis.AsusWinIO64):
        #   HealthyTable_FanCounts()          -> Int32  (count returned directly, no out param)
        #   HealthyTable_SetFanIndex(Byte)    -> Void
        #   HealthyTable_FanRPM()             -> Int32  (RPM of fan set by SetFanIndex, no args)
        #   HealthyTable_SetFanTestMode(Char) -> Void   (Char = 2-byte, pass 0/1)
        #   HealthyTable_SetFanPwmDuty(Int16) -> Void   (ONE arg only: PWM 0-255)
        #   Thermal_Read_Cpu_Temperature()    -> UInt64 (no args, direct return)
        d.InitializeWinIo.restype               = ctypes.c_bool   # returns success flag
        d.InitializeWinIo.argtypes              = []
        d.ShutdownWinIo.restype                 = None
        d.ShutdownWinIo.argtypes                = []
        d.HealthyTable_FanCounts.restype        = ctypes.c_int32  # returns count directly
        d.HealthyTable_FanCounts.argtypes       = []
        d.HealthyTable_SetFanIndex.restype      = None
        d.HealthyTable_SetFanIndex.argtypes     = [ctypes.c_uint8]
        d.HealthyTable_FanRPM.restype           = ctypes.c_int32  # returns RPM, no args
        d.HealthyTable_FanRPM.argtypes          = []
        d.HealthyTable_SetFanTestMode.restype   = None
        d.HealthyTable_SetFanTestMode.argtypes  = [ctypes.c_uint16]  # Char = 2 bytes
        d.HealthyTable_SetFanPwmDuty.restype    = None
        d.HealthyTable_SetFanPwmDuty.argtypes   = [ctypes.c_int16]   # ONE arg: PWM 0-255
        d.Thermal_Read_Cpu_Temperature.restype   = ctypes.c_uint64
        d.Thermal_Read_Cpu_Temperature.argtypes  = []

    def _probe_dll(self):
        d = self._dll
        def try_fn(name, restype, argtypes, *args):
            try:
                fn = getattr(d, name)
                fn.restype  = restype
                fn.argtypes = argtypes
                result = fn(*args)
                return result
            except Exception:
                return None

        count = d.HealthyTable_FanCounts()
        _log(f"probe: FanCounts={count}")
        d.HealthyTable_SetFanTestMode(ctypes.c_uint16(1))
        _log("=== probe done ===")

    def shutdown(self):
        if self._ready and self._dll:
            try:
                self._dll.ShutdownWinIo()
            except Exception:
                pass
            self._ready = False

    def fan_count(self) -> int:
        if not self._ready:
            return 0
        count = self._dll.HealthyTable_FanCounts()  # returns Int32 directly
        if count > 0:
            self._fan_count = count
        if self._fan_count == 0:
            self._fan_count = 1
        return self._fan_count

    def fan_rpm(self, index: int) -> int:
        if not self._ready:
            return 0
        self._dll.HealthyTable_SetFanIndex(ctypes.c_uint8(index))
        return self._dll.HealthyTable_FanRPM()  # returns Int32 directly, no args

    def set_manual_mode(self, on: bool) -> bool:
        if not self._ready:
            return False
        self._dll.HealthyTable_SetFanTestMode(ctypes.c_uint16(1 if on else 0))
        return True

    def set_duty(self, index: int, duty: int) -> bool:
        if not self._ready:
            return False
        duty = max(0, min(100, duty))
        pwm = int(duty * 255 / 100)  # convert percent (0-100) to PWM (0-255)
        self._dll.HealthyTable_SetFanIndex(ctypes.c_uint8(index))
        self._dll.HealthyTable_SetFanPwmDuty(ctypes.c_int16(pwm))  # ONE arg only!
        return True

    def set_all_duty(self, duty: int) -> bool:
        self.set_manual_mode(True)
        count = max(self.fan_count(), 1)
        for i in range(count):
            self.set_duty(i, duty)
        _log(f"set_all_duty({duty}) -> fans={count}")
        return True

    def cpu_temp(self) -> int:
        if not self._ready:
            return -1
        try:
            temp = self._dll.Thermal_Read_Cpu_Temperature()  # returns UInt64 directly
            if 1 < temp < 150:
                return int(temp)
        except Exception:
            pass
        return self._wmi_temp()

    def _wmi_temp(self) -> int:
        now = time.monotonic()
        if hasattr(self, "_wmi_cache_time") and now - self._wmi_cache_time < 20:
            return self._wmi_cache_val
        try:
            import subprocess
            r = subprocess.run(
                ["powershell", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
                 "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi "
                 "| Select-Object -First 1).CurrentTemperature"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            val = r.stdout.strip()
            if val.isdigit():
                celsius = int(val) // 10 - 273
                if 1 < celsius < 150:
                    self._wmi_cache_time = now
                    self._wmi_cache_val  = celsius
                    return celsius
        except Exception:
            pass
        self._wmi_cache_time = now
        self._wmi_cache_val  = -1
        return -1

    def all_rpms(self) -> list[int]:
        count = max(self.fan_count(), 1)
        return [self.fan_rpm(i) for i in range(count)]


# ── Settings ──────────────────────────────────────────────────────────────────

DEFAULTS = {
    "preset":           "auto",
    "fan_enabled":      True,
    "auto_start":       False,
    "minimize_to_tray": True,
    "temp_normal":      TEMP_NORMAL_DEFAULT,
    "temp_medium":      TEMP_MEDIUM_DEFAULT,
    "duty_normal":      DUTY_NORMAL_DEFAULT,
    "duty_medium":      DUTY_MEDIUM_DEFAULT,
    "duty_fast":        DUTY_FAST_DEFAULT,
    "duty_custom":      50,
}

class Settings:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r") as f:
                    self._data.update(json.load(f))
        except Exception:
            pass

    def save(self):
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def __getattr__(self, key):
        try:
            return self._data[key]
        except KeyError:
            return DEFAULTS.get(key)

    def __setattr__(self, key, value):
        if key.startswith("_"):
            super().__setattr__(key, value)
        else:
            self._data[key] = value


# ── Fan Controller ────────────────────────────────────────────────────────────

class FanController:
    def __init__(self, io: AsusWinIO, settings: Settings):
        self._io           = io
        self._s            = settings
        self._mode         = "auto"
        self._enabled      = True
        self._running      = False
        self._thread       = None
        self._current_duty = 0
        self.on_update     = None  # callback(active_preset, temp, rpms, duty)

    @property
    def current_duty(self) -> int:
        return self._current_duty

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, on: bool):
        self._enabled = on
        if not on:
            self._running = False
            self._current_duty = 0
            self._io.set_manual_mode(False)
            _log("fan control disabled, BIOS mode restored")
        else:
            # Re-apply current preset
            self.set_preset(self._mode)

    def set_preset(self, preset: str):
        self._mode = preset
        if not self._enabled:
            return
        if preset == "auto":
            self._ensure_auto_thread()
        else:
            self._running = False
            duty = {
                "normal": self._s.duty_normal,
                "medium": self._s.duty_medium,
                "fast":   self._s.duty_fast,
            }.get(preset, DUTY_NORMAL_DEFAULT)
            self._current_duty = duty
            self._io.set_all_duty(duty)

    def set_custom_duty(self, duty: int):
        """Apply a specific duty% directly (from slider)."""
        if not self._enabled:
            return
        self._running = False
        self._mode = "custom"
        self._current_duty = duty
        self._io.set_all_duty(duty)

    def restore_bios(self):
        self._running = False
        self._current_duty = 0
        self._io.set_manual_mode(False)

    def snapshot(self) -> tuple[int, list[int], int]:
        return self._io.cpu_temp(), self._io.all_rpms(), self._current_duty

    def _ensure_auto_thread(self):
        self._running = True
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._auto_loop, daemon=True)
            self._thread.start()

    def _auto_loop(self):
        while self._running and self._mode == "auto" and self._enabled:
            temp = self._io.cpu_temp()
            if temp > 0:
                if temp < self._s.temp_normal:
                    duty, active = self._s.duty_normal, "normal"
                elif temp < self._s.temp_medium:
                    duty, active = self._s.duty_medium, "medium"
                else:
                    duty, active = self._s.duty_fast, "fast"
                self._current_duty = duty
                self._io.set_all_duty(duty)
                rpms = self._io.all_rpms()
                if self.on_update:
                    self.on_update(active, temp, rpms, duty)
            time.sleep(MONITOR_INTERVAL)


# ── Windows Startup ───────────────────────────────────────────────────────────

def set_auto_start(enabled: bool, launcher: str = ""):
    import subprocess
    action = "/enable" if enabled else "/disable"
    try:
        subprocess.run(
            ["schtasks", "/change", "/tn", "AsusFanControl", action],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10)
        _log(f"autostart task {action}")
    except Exception as e:
        _log(f"autostart: {e}")


# ── Image Helpers ─────────────────────────────────────────────────────────────

def _font(size: int, bold=False) -> ImageFont.ImageFont:
    names = ["arialbd.ttf", "arial.ttf", "segoeui.ttf", "calibri.ttf"] if bold \
       else ["arial.ttf",   "segoeui.ttf", "calibri.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def make_logo(w=160, h=72) -> Image.Image:
    img  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _font(44, bold=True)
    text = "ASUS"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    x    = (w - tw) // 2
    y    = (h - th) // 2 - 4
    for off in range(3, 0, -1):
        alpha = 55 - off * 15
        draw.text((x + off, y + off), text, font=font, fill=(0, 112, 210, alpha))
    draw.text((x, y), text, font=font, fill=(0, 150, 255, 255))
    line_y = y + th + 5
    draw.rectangle([x, line_y, x + tw, line_y + 2], fill=(0, 112, 210, 220))
    return img


def make_tray_icon(color_hex: str = C_ACCENT, size=64) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2
    r  = size // 2 - 4

    def rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    c = rgb(color_hex)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c + (255,), width=3)
    blade_r = r * 0.45
    hub_r   = r * 0.20
    for deg in (0, 90, 180, 270):
        rad  = math.radians(deg)
        rad2 = math.radians(deg + 55)
        bx   = cx + blade_r * math.cos(rad)
        by   = cy + blade_r * math.sin(rad)
        tip_x = cx + (r * 0.72) * math.cos(rad2)
        tip_y = cy + (r * 0.72) * math.sin(rad2)
        br = int(blade_r * 0.38)
        draw.ellipse([bx - br, by - br, bx + br, by + br], fill=c + (230,))
        draw.line([bx, by, tip_x, tip_y], fill=c + (200,), width=3)
    draw.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r], fill=c + (255,))
    return img


# ── Main Window ───────────────────────────────────────────────────────────────

PRESET_META = {
    "normal": dict(label="Normal",      color=C_NORMAL, duty=DUTY_NORMAL_DEFAULT, desc="35%"),
    "medium": dict(label="Equilibrado", color=C_MEDIUM, duty=DUTY_MEDIUM_DEFAULT, desc="50%"),
    "fast":   dict(label="Rápido",      color=C_FAST,   duty=DUTY_FAST_DEFAULT,   desc="100%"),
    "auto":   dict(label="Auto",        color=C_AUTO,   duty=0,                   desc="Auto"),
}

class MainWindow(ctk.CTk):
    def __init__(self, controller: FanController, settings: Settings, app_dir: Path):
        super().__init__()
        self._ctrl     = controller
        self._s        = settings
        self._app_dir  = app_dir
        self._tray     = None
        self._quitting = False
        self._slider_dragging = False

        self.title(APP_NAME)
        self.geometry("440x650")
        self.resizable(False, False)
        self.configure(fg_color=C_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        self._setup_tray()
        self._ctrl.on_update = self._on_auto_update

        # Apply saved state
        enabled = self._s.fan_enabled
        self._fan_enabled_var.set(enabled)
        self._ctrl._enabled = enabled
        self._apply_preset(self._s.preset, save=False)
        self._update_controls_state()
        self._tick()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build(self):
        # Setting vars shared between main window state and Settings dialog
        self._autostart_var = ctk.BooleanVar(value=self._s.auto_start)
        self._tray_var      = ctk.BooleanVar(value=self._s.minimize_to_tray)

        # Menu bar (topmost strip)
        self._build_menubar()

        # Header
        hdr = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=0, height=80)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Logo image — loaded from app dir, fallback to text if missing
        logo_path = self._app_dir / "Imagen1.png"
        try:
            _pil = Image.open(str(logo_path)).convert("RGBA")
            logo_ctk = ctk.CTkImage(_pil, size=(60, 60))
            ctk.CTkLabel(hdr, image=logo_ctk, text="").pack(
                side="left", padx=(16, 0), pady=10)
        except Exception:
            logo_fr = ctk.CTkFrame(hdr, fg_color="transparent")
            logo_fr.pack(side="left", padx=(24, 0), pady=10)
            ctk.CTkLabel(logo_fr, text="ASUS",
                         font=("Segoe UI", 34, "bold"), text_color="#0096ff"
                         ).pack(anchor="w")
            ctk.CTkFrame(logo_fr, fg_color=C_ACCENT, height=2).pack(fill="x", pady=(2, 0))

        title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        title_frame.pack(side="left", fill="both", expand=True, padx=(10, 0))
        ctk.CTkLabel(title_frame, text="Fan Control",
                     font=("Segoe UI", 22, "bold"), text_color=C_TEXT
                     ).pack(anchor="w", pady=(14, 0))
        ctk.CTkLabel(title_frame, text="Advanced Fan Management",
                     font=("Segoe UI", 9), text_color=C_MUTED
                     ).pack(anchor="w")

        # Control toggle
        self._build_toggle()

        # Speed slider
        self._build_slider()

        # Stats cards
        self._build_temp_card()
        self._build_rpm_card()

        # Preset buttons
        self._build_preset_buttons()

        # Auto thresholds (last card — extra bottom padding)
        self._build_thresholds()
        ctk.CTkFrame(self, fg_color="transparent", height=18).pack()

    def _card(self, **kw) -> ctk.CTkFrame:
        f = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=12, **kw)
        f.pack(fill="x", padx=20, pady=(6, 0))
        return f

    def _build_toggle(self):
        card = self._card()
        row  = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)

        self._fan_enabled_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            row,
            text="Controlar velocidad del ventilador",
            variable=self._fan_enabled_var,
            font=("Segoe UI", 13, "bold"),
            text_color=C_TEXT,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT,
            command=self._toggle_fan_control,
        ).pack(side="left")

        self._status_lbl = ctk.CTkLabel(
            row, text="●  Activo",
            font=("Segoe UI", 11), text_color=C_NORMAL)
        self._status_lbl.pack(side="right")

    def _build_slider(self):
        card = self._card()

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(10, 0))
        ctk.CTkLabel(top, text="Velocidad del ventilador",
                     font=("Segoe UI", 12), text_color=C_MUTED).pack(side="left")
        self._speed_pct_lbl = ctk.CTkLabel(
            top, text="-- %",
            font=("Segoe UI", 18, "bold"), text_color=C_TEXT)
        self._speed_pct_lbl.pack(side="right")

        self._slider = ctk.CTkSlider(
            card,
            from_=0, to=100,
            number_of_steps=100,
            height=20,
            button_color=C_ACCENT,
            button_hover_color="#0090ff",
            progress_color=C_ACCENT,
            fg_color=C_BORDER,
            command=self._on_slider_move,
        )
        self._slider.pack(fill="x", padx=16, pady=(6, 14))
        self._slider.set(50)

        # Tick marks for presets
        marks = ctk.CTkFrame(card, fg_color="transparent")
        marks.pack(fill="x", padx=16, pady=(0, 10))
        for pct, lbl in [(0, "0%"), (35, "35%"), (50, "50%"), (100, "100%")]:
            ctk.CTkLabel(marks, text=lbl,
                         font=("Segoe UI", 9), text_color=C_MUTED).place(
                relx=pct / 100, anchor="n")
        marks.configure(height=14)
        marks.pack_propagate(False)

    def _build_temp_card(self):
        card = self._card()
        row  = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(row, text="Temperatura CPU",
                     font=("Segoe UI", 12), text_color=C_MUTED).pack(side="left")
        self._temp_lbl = ctk.CTkLabel(
            row, text="-- °C", font=("Segoe UI", 28, "bold"), text_color=C_TEXT)
        self._temp_lbl.pack(side="right")

        self._temp_bar = ctk.CTkProgressBar(
            card, height=6, corner_radius=3,
            progress_color=C_NORMAL, fg_color=C_BORDER)
        self._temp_bar.pack(fill="x", padx=16, pady=(0, 10))
        self._temp_bar.set(0)

    def _build_rpm_card(self):
        card = self._card()
        row  = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(row, text="Velocidad actual",
                     font=("Segoe UI", 12), text_color=C_MUTED).pack(side="left")
        self._rpm_lbl = ctk.CTkLabel(
            row, text="--", font=("Segoe UI", 20, "bold"), text_color=C_TEXT)
        self._rpm_lbl.pack(side="right")

    def _build_preset_buttons(self):
        self._mode_lbl = ctk.CTkLabel(
            self, text="Modo: Automático",
            font=("Segoe UI", 13, "bold"), text_color=C_AUTO)
        self._mode_lbl.pack(pady=(10, 4))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=4)
        grid.columnconfigure((0, 1, 2, 3), weight=1, uniform="b")

        self._btns: dict[str, ctk.CTkButton] = {}
        for col, (key, meta) in enumerate(PRESET_META.items()):
            btn = ctk.CTkButton(
                grid,
                text=f"{meta['label']}\n{meta['desc']}",
                font=("Segoe UI", 11, "bold"),
                fg_color=C_CARD,
                hover_color="#2a2a2a",
                text_color=meta["color"],
                border_color=C_BORDER,
                border_width=1,
                corner_radius=10,
                height=56,
                command=lambda k=key: self._apply_preset(k),
            )
            btn.grid(row=0, column=col, padx=3, sticky="ew")
            self._btns[key] = btn

    def _build_thresholds(self):
        card = self._card()
        ctk.CTkLabel(card, text="Umbrales modo automático",
                     font=("Segoe UI", 10), text_color=C_MUTED).pack(
                     anchor="w", padx=16, pady=(10, 2))

        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(0, 2))
        ctk.CTkLabel(row1, text="Normal  →  Equilibrado",
                     font=("Segoe UI", 11), text_color=C_TEXT).pack(side="left")
        self._t1_lbl = ctk.CTkLabel(
            row1, text=f"{self._s.temp_normal}°C",
            font=("Segoe UI", 11, "bold"), text_color=C_MEDIUM)
        self._t1_lbl.pack(side="right")

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(row2, text="Equilibrado  →  Rápido",
                     font=("Segoe UI", 11), text_color=C_TEXT).pack(side="left")
        self._t2_lbl = ctk.CTkLabel(
            row2, text=f"{self._s.temp_medium}°C",
            font=("Segoe UI", 11, "bold"), text_color=C_FAST)
        self._t2_lbl.pack(side="right")

    def _build_menubar(self):
        bar = ctk.CTkFrame(self, fg_color="#111111", corner_radius=0, height=28)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        self._cfg_btn = ctk.CTkButton(
            bar, text="  Configuración  ", font=("Segoe UI", 11),
            fg_color="transparent", hover_color="#252525",
            text_color=C_MUTED, height=28, corner_radius=0,
            command=self._show_settings_menu,
        )
        self._cfg_btn.pack(side="left")

        ctk.CTkButton(
            bar, text="  Acerca de  ", font=("Segoe UI", 11),
            fg_color="transparent", hover_color="#252525",
            text_color=C_MUTED, height=28, corner_radius=0,
            command=self._open_about,
        ).pack(side="left")

    def _show_settings_menu(self):
        import tkinter as tk

        def do_autostart():
            self._autostart_var.set(not self._autostart_var.get())
            self._toggle_autostart()

        def do_tray():
            self._tray_var.set(not self._tray_var.get())
            self._toggle_tray()

        chk = "✓  "
        off = "     "
        m = tk.Menu(self, tearoff=0,
                    bg="#1e1e1e", fg="#e0e0e0",
                    activebackground="#0070d2", activeforeground="#ffffff",
                    relief="flat", bd=1, font=("Segoe UI", 11))
        m.add_command(
            label=f"{chk if self._autostart_var.get() else off}Iniciar con Windows",
            command=do_autostart)
        m.add_command(
            label=f"{chk if self._tray_var.get() else off}Minimizar a bandeja al cerrar",
            command=do_tray)

        x = self._cfg_btn.winfo_rootx()
        y = self._cfg_btn.winfo_rooty() + self._cfg_btn.winfo_height()
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _open_about(self):
        import webbrowser
        win = ctk.CTkToplevel(self)
        win.title("Acerca de")
        win.geometry("390x270")
        win.resizable(False, False)
        win.configure(fg_color=C_BG)
        win.grab_set()
        win.after(50, win.lift)

        ctk.CTkLabel(win, text="ASUS Fan Control",
                     font=("Segoe UI", 18, "bold"), text_color=C_ACCENT
                     ).pack(pady=(20, 2))
        ctk.CTkLabel(win, text=f"Versión {APP_VERSION}",
                     font=("Segoe UI", 11), text_color=C_MUTED
                     ).pack()

        ctk.CTkFrame(win, fg_color=C_BORDER, height=1).pack(fill="x", padx=20, pady=12)

        ctk.CTkLabel(win, text="Modificado por  xd-Programmer-IA",
                     font=("Segoe UI", 11, "bold"), text_color=C_TEXT).pack()
        lnk1 = ctk.CTkLabel(win,
                     text="github.com/xd-Programmer-IA/AsusFanControl",
                     font=("Segoe UI", 10), text_color=C_ACCENT, cursor="hand2")
        lnk1.pack()
        lnk1.bind("<Button-1>",
                  lambda _: webbrowser.open("https://github.com/xd-Programmer-IA/AsusFanControl"))

        ctk.CTkLabel(win, text="", font=("Segoe UI", 5)).pack()

        ctk.CTkLabel(win, text="Creado por  Karmel0x",
                     font=("Segoe UI", 11, "bold"), text_color=C_TEXT).pack()
        lnk2 = ctk.CTkLabel(win,
                     text="github.com/Karmel0x",
                     font=("Segoe UI", 10), text_color=C_MUTED, cursor="hand2")
        lnk2.pack()
        lnk2.bind("<Button-1>",
                  lambda _: webbrowser.open("https://github.com/Karmel0x"))

        ctk.CTkButton(win, text="Cerrar", command=win.destroy,
                      fg_color=C_ACCENT, hover_color="#0090ff", width=90
                      ).pack(pady=16)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _toggle_fan_control(self):
        enabled = self._fan_enabled_var.get()
        self._s.fan_enabled = enabled
        self._s.save()
        self._ctrl.set_enabled(enabled)
        self._update_controls_state()

    def _update_controls_state(self):
        enabled = self._fan_enabled_var.get()
        if enabled:
            self._status_lbl.configure(text="●  Activo",    text_color=C_NORMAL)
            self._slider.configure(state="normal")
            for btn in self._btns.values():
                btn.configure(state="normal")
        else:
            self._status_lbl.configure(text="●  Desactivado", text_color=C_MUTED)
            self._slider.configure(state="disabled")
            for btn in self._btns.values():
                btn.configure(state="disabled")
            self._mode_lbl.configure(text="Control BIOS", text_color=C_MUTED)
            self._rpm_lbl.configure(text="BIOS")
            self._speed_pct_lbl.configure(text="-- %")

    def _on_slider_move(self, value: float):
        duty = int(value)
        self._speed_pct_lbl.configure(text=f"{duty} %")
        # Deselect all preset buttons (custom speed)
        self._highlight_preset(None)
        self._mode_lbl.configure(text=f"Manual: {duty}%", text_color=C_ACCENT)
        # Apply with a short debounce — only send to DLL when slider stops
        if hasattr(self, "_slider_after"):
            self.after_cancel(self._slider_after)
        self._slider_after = self.after(150, lambda d=duty: self._ctrl.set_custom_duty(d))

    def _apply_preset(self, preset: str, save=True):
        _log(f"apply_preset: {preset}")
        self._ctrl.set_preset(preset)
        meta = PRESET_META[preset]

        self._highlight_preset(preset)
        self._mode_lbl.configure(text=f"Modo: {meta['label']}", text_color=meta["color"])

        # Move slider to match preset duty (not for auto)
        if preset != "auto":
            duty = {
                "normal": self._s.duty_normal,
                "medium": self._s.duty_medium,
                "fast":   self._s.duty_fast,
            }.get(preset, 50)
            self._slider.set(duty)
            self._speed_pct_lbl.configure(text=f"{duty} %")

        if save:
            self._s.preset = preset
            self._s.save()

    def _highlight_preset(self, active: str | None):
        for key, btn in self._btns.items():
            m = PRESET_META[key]
            if key == active:
                btn.configure(fg_color=m["color"], text_color=C_WHITE,
                               border_color=m["color"])
            else:
                btn.configure(fg_color=C_CARD, text_color=m["color"],
                               border_color=C_BORDER)

    def _toggle_autostart(self):
        enabled = self._autostart_var.get()
        self._s.auto_start = enabled
        self._s.save()
        launcher = str(self._app_dir / "run_v2.bat")
        set_auto_start(enabled, launcher)

    def _toggle_tray(self):
        self._s.minimize_to_tray = self._tray_var.get()
        self._s.save()

    def _on_close(self):
        if self._s.minimize_to_tray:
            self.withdraw()
        else:
            self._quit()

    def _quit(self):
        if self._quitting:
            return
        self._quitting = True
        self._ctrl.restore_bios()
        if self._tray:
            self._tray.stop()
        self.destroy()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def _tick(self):
        def _work():
            try:
                temp, rpms, duty = self._ctrl.snapshot()
                _log(f"tick: temp={temp} duty={duty}")
                self.after(0, lambda: self._refresh_ui(temp, rpms, duty))
            except Exception as e:
                _log(f"tick ERROR: {e}")
        threading.Thread(target=_work, daemon=True).start()
        self.after(STATS_INTERVAL, self._tick)

    def _on_auto_update(self, active, temp, rpms, duty):
        self.after(0, lambda: self._on_auto_ui(active, temp, rpms, duty))

    def _on_auto_ui(self, active, temp, rpms, duty):
        self._refresh_ui(temp, rpms, duty)
        self._highlight_preset(active)
        meta = PRESET_META.get(active, PRESET_META["auto"])
        self._mode_lbl.configure(text=f"Auto → {meta['label']}", text_color=meta["color"])
        # Move slider to show current auto speed
        self._slider.set(duty)
        self._speed_pct_lbl.configure(text=f"{duty} %")

    def _refresh_ui(self, temp: int, rpms: list[int], duty: int = 0):
        if not self._fan_enabled_var.get():
            return

        # Temperature
        if temp > 0:
            self._temp_lbl.configure(text=f"{temp} °C")
            if temp < self._s.temp_normal:
                col = C_NORMAL
            elif temp < self._s.temp_medium:
                col = C_MEDIUM
            else:
                col = C_FAST
            self._temp_lbl.configure(text_color=col)
            self._temp_bar.configure(progress_color=col)
            self._temp_bar.set(min(temp / 100.0, 1.0))

        # Fan speed: show RPM if available, otherwise duty%
        if rpms:
            max_rpm = max(rpms)
            if max_rpm > 0:
                self._rpm_lbl.configure(text=f"{max_rpm:,} RPM")
            elif duty > 0:
                self._rpm_lbl.configure(text=f"{duty}%")
            else:
                self._rpm_lbl.configure(text="Auto")

        # Update slider label if not in auto mode (auto updates it via _on_auto_ui)
        if self._ctrl._mode != "auto" and duty > 0 and not self._slider_dragging:
            self._speed_pct_lbl.configure(text=f"{duty} %")

    # ── System Tray ───────────────────────────────────────────────────────────

    def _setup_tray(self):
        from pystray import Icon, Menu, MenuItem as Item

        icon_img = make_tray_icon(C_ACCENT)
        menu = Menu(
            Item("Mostrar ventana", self._tray_show, default=True),
            Menu.SEPARATOR,
            Item("Normal",      lambda _: self.after(0, lambda: self._apply_preset("normal"))),
            Item("Equilibrado", lambda _: self.after(0, lambda: self._apply_preset("medium"))),
            Item("Rápido",      lambda _: self.after(0, lambda: self._apply_preset("fast"))),
            Item("Auto",        lambda _: self.after(0, lambda: self._apply_preset("auto"))),
            Menu.SEPARATOR,
            Item("Salir", self._tray_quit),
        )
        self._tray = Icon(APP_NAME, icon_img, APP_NAME, menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _tray_show(self, _=None):
        self.after(0, self.deiconify)
        self.after(0, self.lift)

    def _tray_quit(self, _=None):
        self.after(0, self._quit)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent

    dll_path = str(app_dir / "AsusWinIO64.dll")

    io = AsusWinIO(dll_path)
    if not io.initialize():
        import tkinter.messagebox as mb
        mb.showerror(
            APP_NAME,
            "No se pudo inicializar AsusWinIO64.dll.\n\n"
            "Asegúrese de ejecutar la aplicación mediante run_v2.bat\n"
            "(requiere permisos de SYSTEM a través de PsExec)."
        )
        sys.exit(1)

    settings   = Settings()
    controller = FanController(io, settings)

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = MainWindow(controller, settings, app_dir)
    try:
        app.mainloop()
    finally:
        io.shutdown()


if __name__ == "__main__":
    main()
