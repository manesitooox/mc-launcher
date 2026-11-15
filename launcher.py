"""Launcher de Minecraft con auto-actualización desde GitHub."""
import hashlib
import json
import queue
import re
import subprocess
import threading
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import messagebox, ttk

import minecraft_launcher_lib as mll

import updater

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path.home() / ".mi_launcher"
MC_DIR = DATA_DIR / "minecraft"
SETTINGS_FILE = DATA_DIR / "settings.json"


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def offline_uuid(name: str) -> str:
    h = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode()).digest())
    h[6] = (h[6] & 0x0F) | 0x30
    h[8] = (h[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(h)))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.cfg = load_json(APP_DIR / "config.json", {})
        self.settings = load_json(SETTINGS_FILE, {"username": "Jugador", "ram": 4096})
        vfile = APP_DIR / "VERSION"
        self.version = vfile.read_text().strip() if vfile.exists() else "0"
        self.q = queue.Queue()
        self._max, self._val = 1, 0

        self.title(f"{self.cfg.get('name', 'Mi Launcher')}  v{self.version}")
        self.geometry("420x300")
        self.resizable(False, False)
        self._build_ui()
        self.after(100, self._poll)
        threading.Thread(target=self._startup, daemon=True).start()

    # ---------- UI ----------
    def _build_ui(self):
        pad = {"padx": 24, "pady": 6}
        ttk.Label(self, text=self.cfg.get("name", "Mi Launcher"),
                  font=("Segoe UI", 18, "bold")).pack(pady=(18, 6))
        ttk.Label(self, text=f"Minecraft {self.cfg.get('minecraft_version', '1.20.1')} · "
                             f"{self.cfg.get('mod_loader', 'vanilla')}").pack()

        row = ttk.Frame(self); row.pack(fill="x", **pad)
        ttk.Label(row, text="Usuario:", width=9).pack(side="left")
        self.user_var = tk.StringVar(value=self.settings.get("username", "Jugador"))
        ttk.Entry(row, textvariable=self.user_var).pack(side="left", fill="x", expand=True)

        row = ttk.Frame(self); row.pack(fill="x", **pad)
        ttk.Label(row, text="RAM (MB):", width=9).pack(side="left")
        self.ram_var = tk.StringVar(value=str(self.settings.get("ram", 4096)))
        ttk.Spinbox(row, from_=1024, to=32768, increment=512,
                    textvariable=self.ram_var, width=10).pack(side="left")

        self.bar = ttk.Progressbar(self, maximum=1, value=0)
        self.bar.pack(fill="x", padx=24, pady=(14, 4))
        self.status_var = tk.StringVar(value="Iniciando…")
        ttk.Label(self, textvariable=self.status_var).pack()

        self.btn = ttk.Button(self, text="JUGAR", command=self._on_play, state="disabled")
        self.btn.pack(pady=14, ipadx=30, ipady=6)

    def _poll(self):
        try:
            while True:
                kind, *a = self.q.get_nowait()
                if kind == "status":
                    self.status_var.set(a[0])
                elif kind == "progress":
                    self.bar.configure(maximum=max(a[1], 1), value=a[0])
                elif kind == "busy":
                    self.btn.configure(state="disabled")
                elif kind == "ready":
                    self.btn.configure(state="normal")
                elif kind == "error":
                    messagebox.showerror("Error", a[0])
                elif kind == "restart":
                    self.destroy()
                    updater.restart()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def status(self, text):
        self.q.put(("status", text))

    # ---------- Arranque: actualizaciones ----------
    def _startup(self):
        self.q.put(("busy",))
        try:
            repo = self.cfg.get("launcher_repo", "")
            if updater.is_configured(repo):
                self.status("Buscando actualizaciones del launcher…")
                if updater.self_update(repo, APP_DIR, self.status):
                    self.status("Reiniciando con la nueva versión…")
                    self.q.put(("restart",))
                    return
        except Exception as e:
            self.status(f"No se pudo actualizar el launcher: {e}")

        try:
            repo = self.cfg.get("modpack_repo", "")
            if updater.is_configured(repo):
                self.status("Buscando actualizaciones del modpack…")
                updater.sync_modpack(repo, MC_DIR, self.status)
        except Exception as e:
            self.status(f"No se pudo actualizar el modpack: {e}")

        self.status("Listo para jugar")
        self.q.put(("ready",))

    # ---------- Jugar ----------
    def _on_play(self):
        name = self.user_var.get().strip()
        if not re.fullmatch(r"\w{3,16}", name):
            messagebox.showwarning("Usuario", "Usa 3-16 caracteres (letras, números o _).")
            return
        try:
            ram = int(self.ram_var.get())
        except ValueError:
            messagebox.showwarning("RAM", "La RAM debe ser un número.")
            return
        self.settings.update(username=name, ram=ram)
        SETTINGS_FILE.write_text(json.dumps(self.settings), encoding="utf-8")
        self.q.put(("busy",))
        threading.Thread(target=self._play, args=(name, ram), daemon=True).start()

    def _install(self) -> str:
        mc = self.cfg.get("minecraft_version", "1.20.1")
        loader = self.cfg.get("mod_loader", "vanilla")
        cb = {
            "setStatus": lambda t: self.status(t),
            "setProgress": lambda v: self._set_progress(val=v),
            "setMax": lambda m: self._set_progress(mx=m),
        }
        if loader == "fabric":
            vid = f"fabric-loader-{mll.fabric.get_latest_loader_version()}-{mc}"
            if not (MC_DIR / "versions" / vid / f"{vid}.json").exists():
                self.status("Instalando Fabric…")
                mll.fabric.install_fabric(mc, str(MC_DIR), callback=cb)
            return vid
        self.status("Verificando archivos de Minecraft…")
        mll.install.install_minecraft_version(mc, str(MC_DIR), callback=cb)
        return mc

    def _set_progress(self, val=None, mx=None):
        if mx is not None:
            self._max = mx
        if val is not None:
            self._val = val
        self.q.put(("progress", self._val, self._max))

    def _play(self, name, ram):
        try:
            vid = self._install()
            options = {
                "username": name,
                "uuid": offline_uuid(name),
                "token": "",
                "jvmArguments": [f"-Xmx{ram}M", f"-Xms{min(ram, 1024)}M"],
            }
            cmd = mll.command.get_minecraft_command(vid, str(MC_DIR), options)
            self.status("Iniciando Minecraft…")
            subprocess.Popen(cmd, cwd=str(MC_DIR))
            self.status("Minecraft iniciado")
        except Exception as e:
            self.q.put(("error", str(e)))
        finally:
            self.q.put(("ready",))


if __name__ == "__main__":
    App().mainloop()
