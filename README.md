# Mi Launcher de Minecraft (auto-actualizable vía GitHub)

## Instalación
1. Instala Python 3.9+ y Java (si el launcher no descarga uno solo).
2. `pip install -r requirements.txt`
3. `python launcher.py`

## Configurar tu GitHub
1. Crea un repo (ej. `tuusuario/mi-launcher`) y sube estos archivos (incluida la carpeta `.github`).
2. Edita `config.json` → `"launcher_repo": "tuusuario/mi-launcher"`.
3. Para publicar una versión nueva:
   ```
   git tag v1.0.1
   git push origin v1.0.1
   ```
   GitHub Actions crea el release con `launcher.zip`. La próxima vez que
   alguien abra el launcher, se descarga la versión nueva y se reinicia solo.

## Actualizar mods/configs (opcional)
1. Crea otro repo para el modpack y ponlo en `"modpack_repo"`.
2. En cada release adjunta un `modpack.zip` con la estructura de la carpeta
   del juego (`mods/`, `config/`, `resourcepacks/`…).
3. El launcher borra los archivos de la versión anterior y extrae los nuevos.

## Cambiar la versión de Minecraft
Edita `minecraft_version` y `mod_loader` (`vanilla` o `fabric`) en `config.json`,
publica un release nuevo y todos se actualizan.

## Datos
Todo se guarda en `~/.mi_launcher/` (juego + ajustes del jugador).
Los repos deben ser públicos (o añade un token a `updater.py`).
