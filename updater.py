"""Auto-actualización mediante GitHub Releases (solo librería estándar)."""
import io
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.github.com/repos/{repo}/releases/latest"


def is_configured(repo: str) -> bool:
    return bool(repo) and "TU_USUARIO" not in repo


def _request(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "mc-launcher", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def latest_release(repo: str):
    """Devuelve el JSON del último release o None si no hay ninguno."""
    try:
        return json.loads(_request(API.format(repo=repo)))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _vtuple(v: str):
    return tuple(int(n) for n in re.findall(r"\d+", v))


def _extract(zf: zipfile.ZipFile, dest: Path, strip_top: bool = False):
    """Extrae el zip (protegido contra zip-slip). Devuelve las rutas escritas."""
    dest = Path(dest).resolve()
    names = [i.filename for i in zf.infolist() if not i.is_dir()]
    prefix = ""
    if strip_top and names:
        tops = {n.split("/")[0] for n in names}
        if len(tops) == 1 and all("/" in n for n in names):
            prefix = tops.pop() + "/"
    written = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename[len(prefix):] if prefix else info.filename
        if not name:
            continue
        target = (dest / name).resolve()
        if dest not in target.parents:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)
        written.append(Path(name).as_posix())
    return written


def self_update(repo: str, app_dir: Path, log=print) -> bool:
    """Actualiza el propio launcher. True si se instaló una versión nueva."""
    app_dir = Path(app_dir)
    vfile = app_dir / "VERSION"
    current = vfile.read_text().strip() if vfile.exists() else "0"

    rel = latest_release(repo)
    if not rel:
        return False
    tag = rel["tag_name"]
    if _vtuple(tag) <= _vtuple(current):
        log("Launcher actualizado")
        return False

    log(f"Descargando launcher {tag}…")
    asset = next((a for a in rel.get("assets", []) if a["name"] == "launcher.zip"), None)
    url = asset["browser_download_url"] if asset else rel["zipball_url"]
    data = _request(url)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        _extract(zf, app_dir, strip_top=True)
    vfile.write_text(tag.lstrip("vV"))
    return True


def sync_modpack(repo: str, game_dir: Path, log=print) -> bool:
    """Descarga modpack.zip del último release y lo extrae en la carpeta del juego.

    Borra los archivos que instaló la versión anterior (mods eliminados, etc.).
    """
    game_dir = Path(game_dir)
    game_dir.mkdir(parents=True, exist_ok=True)
    state_file = game_dir / ".modpack_state.json"
    try:
        state = json.loads(state_file.read_text())
    except Exception:
        state = {}

    rel = latest_release(repo)
    if not rel:
        return False
    tag = rel["tag_name"]
    if state.get("tag") == tag:
        log("Modpack actualizado")
        return False

    asset = next((a for a in rel.get("assets", []) if a["name"] == "modpack.zip"), None)
    if not asset:
        log("El release del modpack no tiene modpack.zip")
        return False

    log(f"Descargando modpack {tag}…")
    data = _request(asset["browser_download_url"])

    for old in state.get("files", []):
        p = game_dir / old
        if p.is_file():
            p.unlink()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        files = _extract(zf, game_dir)
    state_file.write_text(json.dumps({"tag": tag, "files": files}))
    return True


def restart():
    """Reinicia el launcher con los archivos nuevos."""
    subprocess.Popen([sys.executable] + sys.argv)
    sys.exit(0)
