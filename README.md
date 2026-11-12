# SimRCL by Dead_wall

SimReady Central Library: a browser and importer for NVIDIA SimReady assets inside Cinema 4D. Search the catalog, download a package and get the model in your scene with a clean hierarchy, correct scale, materials for your renderer and controls for its moving parts.

Latest version: see [Releases](https://github.com/denwerdan-arch/SimRCL/releases/latest). Code license: MIT. Every asset has its own license (see below).
Author: Dead_wall, https://trycad.online/?lang=en

SimRCL is an independent project. It is not made, endorsed or supported by NVIDIA, Maxon, Redshift, Autodesk, Chaos or OTOY.

## Установка (Windows)

### 1. Python 3 (один раз)

Cinema 4D не умеет сама читать материалы USD, поэтому SimRCL читает их маленьким отдельным процессом на Python. Python нужен только для этого, работать с ним руками не придётся.

1. Откройте https://www.python.org/downloads/windows/, нажмите ссылку **Latest Python 3 Release - Python 3.x.x**, внизу открывшейся страницы скачайте **Windows installer (64-bit)**. Нужен именно этот классический установщик: в нём есть галочка из следующего шага.
2. Запустите скачанный файл. **На первом экране внизу поставьте галочку «Add python.exe to PATH»**: так SimRCL гарантированно найдёт Python.
3. Нажмите **Install Now** и дождитесь конца установки.
4. Проверка (по желанию): Win+R, введите `cmd`, Enter, в чёрном окне наберите `py --version`. Должно появиться `Python 3.x.x`.

Если Python уже стоит, этот шаг пропустите: установщик SimRCL сам проверит и подскажет, если что-то не так.

### 2. SimRCL

1. Скачайте `SimRCL_by_Dead_wall_v<версия>.zip` из [последнего релиза](https://github.com/denwerdan-arch/SimRCL/releases/latest) и распакуйте целиком.
2. Дважды щёлкните `INSTALL.bat`.
3. Перезапустите Cinema 4D и откройте Extensions > SimRCL by Dead_wall. Окно можно встроить в интерфейс и сохранить в макете.

Установщик кладёт плагин `SimRCL` в папку `plugins` всех найденных Cinema 4D 2026 и заранее ставит `usd-core` (библиотеку для чтения USD, около 30 МБ) в отдельную папку SimRCL, не трогая ваш Python. Если плагин уже стоял, старая копия переносится в `%APPDATA%\SRC by Deadwall\backup` (ничего не удаляется).

Обновление: SimRCL сам сообщит о новой версии кнопкой «Update» рядом с названием. Скачайте архив, запустите его `INSTALL.bat` и перезапустите Cinema 4D.

Ручная установка (и macOS, не проверялась): Cinema 4D > Edit > Preferences > Open Preferences Folder > `plugins`, скопируйте туда папку `SimRCL` из архива, перезапустите Cinema 4D.

Удаление: удалите папку `SimRCL` из `plugins`. Скачанные ассеты лежат в `Documents\SRC by Deadwall`.

## Install (Windows)

### 1. Python 3 (once)

Cinema 4D cannot read USD materials itself, so SimRCL reads them in a small separate Python process. You never have to use Python yourself.

1. Open https://www.python.org/downloads/windows/, click **Latest Python 3 Release - Python 3.x.x** and, at the bottom of that page, download **Windows installer (64-bit)**. Take this classic installer: it has the check box of the next step.
2. Run the installer. **On its first screen tick "Add python.exe to PATH"** at the bottom, so SimRCL is sure to find Python.
3. Click **Install Now** and wait for it to finish.
4. Optional check: Win+R, type `cmd`, Enter, then `py --version`; it should print `Python 3.x.x`.

Already have Python 3? Skip this; the SimRCL installer checks and tells you if something is missing.

### 2. SimRCL

1. Download `SimRCL_by_Dead_wall_v<version>.zip` from the [latest release](https://github.com/denwerdan-arch/SimRCL/releases/latest) and unpack all of it.
2. Double-click `INSTALL.bat`.
3. Restart Cinema 4D and open Extensions > SimRCL by Dead_wall. The window can be docked and saved in a layout.

The installer puts the `SimRCL` plugin into `plugins` of every Cinema 4D 2026 it finds and installs `usd-core` (the USD library, about 30 MB) into SimRCL's own folder, leaving your Python untouched. A plugin that was already there is moved to `%APPDATA%\SRC by Deadwall\backup` (nothing is deleted).

Updates: SimRCL shows an "Update" button next to its name when a new version is out. Download it, run its `INSTALL.bat`, restart Cinema 4D.

Manual install: Edit > Preferences > Open Preferences Folder > `plugins`, copy the `SimRCL` folder from the archive there, restart Cinema 4D.

## Features

- Search: natural language, keywords or both, with the catalog's match percentages; categories, providers (OEMs, ISVs, DSX), mass, licence and size filters (min / max per axis, as on the site), sorting, grid and list views.
- Asset details from the catalog: provider, author, polygons, mass, physics, description and tags; 360 degree and moving-parts video previews; similar assets.
- Downloads with progress, a local library, re-download, custom download folder.
- Import into the active document:
  - clean hierarchy, parts parented through the asset's physics joints, axes on the joints;
  - controls for moving parts (rotate or slide within the joint's limits);
  - scale baked into the geometry, Area Weighted Phong normals, colliders hidden, one layer per asset;
  - optional: meshes made of loose triangles (STL conversions) welded into connected surfaces (Settings, off by default);
  - one-mesh models split into one object per material (only when the parts of different materials share no points);
  - materials for Redshift, Standard, Arnold, V-Ray and Octane, OpenPBR where the renderer has it;
  - texture repeat from USD with UV controls on the model (Auto / Custom / Off);
  - Round corners on the model for Redshift, Arnold, V-Ray and Octane (off until switched on, default radius 0.1 cm).
- Licensing guide (English and Russian) in the Settings menu.
- Update check: once a day the window asks GitHub for a newer release and shows an "Update" button next to the name (Settings: "Check for updates now", "Check for updates on start"). The request goes to api.github.com and carries nothing about you or your scenes.
- For AI agents: `simready_agent.py` (search, download, import with short text answers), [AGENTS.md](AGENTS.md) (how the code works, how to port it) and a [skill](for_agents/skills/simrcl-cinema4d/SKILL.md).

## Requirements

- Cinema 4D 2026 on Windows (developed and tested on 2026.4).
- Python 3 with pip (`py -3`, `python3` or `python`).
- Internet access to the catalog service (NVIDIA's Hugging Face Space, `nvidia-simready-central.hf.space`) and to Hugging Face for downloads. SimRCL uses the Space's search API, which NVIDIA may change; assets already downloaded keep importing.

## Where things are stored

- Downloaded packages: `Documents\SRC by Deadwall\Assets` (or your folder from Settings).
- Settings: `%APPDATA%\SRC by Deadwall\settings.json`.
- USD runtime: `%LOCALAPPDATA%\SRC by Deadwall\usd_runtime`. Catalog and preview cache: `simready_cache` in the temp folder.

The data folders carry the project's working name, "SRC by Deadwall".

## Licenses of the assets

SimRCL only downloads assets; their authors set the licenses (most are CC BY 4.0, which requires attribution and a note of your changes). Read the Licensing guide in Settings and the License row in the details before commercial use.

## Troubleshooting

- "Python 3 was not found": install Python 3 as described above (with "Add python.exe to PATH") and run `INSTALL.bat` again. If Python is installed without that box, run its installer again, choose Modify, and tick "Add Python to environment variables".
- Search shows nothing: the catalog is a Hugging Face Space and can take a minute to wake up on the first request.
- Model imported without materials or controls: the status line says why; the details are in the Python console (Shift+F10). Running `INSTALL.bat` again repairs the USD runtime.
- Errors: copy the console text into a bug report.

## Development

```
SimRCL.pyp            plugin entry: puts simready_lib on sys.path, registers Extensions > SimRCL by Dead_wall (ID 1073247)
res/                  plugin icon
simready_lib/         all modules (see AGENTS.md for which are portable and which use Cinema 4D)
tests/                sandbox tests, plain scripts: python tools/run_tests.py
installer/            INSTALL.bat + install.ps1 shipped at the top of the release zip
for_agents/           skill for agents that drive Cinema 4D through an MCP
tools/                build_release.py, release_notes.py, run_tests.py, make_icons.py
```

To work on a checkout inside Cinema 4D, copy or link this folder into the preferences' `plugins` folder (Cinema 4D loads only `SimRCL.pyp`; tests and tools are ignored) and restart.

Releasing an update:

1. Change `VERSION` in `simready_lib/simready_ui.py` and add a `## <version>` section on top of `CHANGELOG.md`.
2. Commit, then tag and push: `git tag v<version> && git push origin main v<version>`.
3. The `release` workflow runs the tests, builds `SimRCL_by_Dead_wall_v<version>.zip` and publishes the release with that changelog section as its notes.
