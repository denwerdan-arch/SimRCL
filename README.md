# SimRCL by Dead_wall

SimReady Central Library: a browser and importer for NVIDIA SimReady assets inside Cinema 4D. Search the catalog, download a package and get the model in your scene with a clean hierarchy, correct scale, materials for your renderer and controls for its moving parts.

Version 1.1.0. Code license: MIT. Every asset has its own license (see below).
Author: Dead_wall, https://trycad.online/?lang=en

SimRCL is an independent project. It is not made, endorsed or supported by NVIDIA, Maxon, Redshift, Autodesk or Chaos.

## Установка (Windows)

1. Скачайте `SimRCL_by_Dead_wall_v<версия>.zip` из [последнего релиза](../../releases/latest) и распакуйте целиком.
2. Дважды щёлкните `INSTALL.bat`.
3. Перезапустите Cinema 4D и откройте Extensions > SimRCL by Dead_wall. Окно можно встроить в интерфейс и сохранить в макете.

Установщик копирует плагин `SimRCL` в папку `plugins` всех найденных Cinema 4D 2026, прежние копии (плагин и старые скриптовые версии SimRCL / SimRS) переносит в резервную папку `%APPDATA%\SRC by Deadwall\backup` (ничего не удаляет) и заранее ставит `usd-core` для чтения USD. Обновление: запустите `INSTALL.bat` новой версии и перезапустите Cinema 4D.

Нужен Python 3 (https://www.python.org/downloads/, при установке отметьте "Add python.exe to PATH"). Cinema 4D не умеет читать материалы USD сама, поэтому SimRCL читает их отдельным процессом через `usd-core`, который ставит в свою папку. Если Python нет, установщик подскажет; поставьте его и запустите `INSTALL.bat` ещё раз.

Ручная установка (и macOS, не проверялась): Cinema 4D > Edit > Preferences > Open Preferences Folder > `plugins`, скопируйте туда папку `SimRCL`, перезапустите Cinema 4D.

Удаление: удалите папку `SimRCL` из `plugins`. Скачанные ассеты лежат в `Documents\SRC by Deadwall`.

## Install (Windows)

1. Download `SimRCL_by_Dead_wall_v<version>.zip` from the [latest release](../../releases/latest) and unpack all of it.
2. Double-click `INSTALL.bat`.
3. Restart Cinema 4D and open Extensions > SimRCL by Dead_wall. The window can be docked and saved in a layout.

The installer copies the `SimRCL` plugin into `plugins` of every Cinema 4D 2026 it finds, moves earlier copies (the plugin and the old script versions SimRCL / SimRS) to `%APPDATA%\SRC by Deadwall\backup` (nothing is deleted) and installs `usd-core` ahead of the first import. To update, run the new version's `INSTALL.bat` and restart Cinema 4D. Python 3 is required (python.org, tick "Add python.exe to PATH").

Manual install: Edit > Preferences > Open Preferences Folder > `plugins`, copy the `SimRCL` folder there, restart Cinema 4D.

## Features

- Search: natural language, keywords or both, with the catalog's match percentages; categories, providers (OEMs, ISVs, DSX), mass, licence and size filters (min / max per axis, as on the site), sorting, grid and list views.
- Asset details from the catalog: provider, author, polygons, mass, physics, description and tags; 360 degree and moving-parts video previews; similar assets.
- Downloads with progress, a local library, re-download, custom download folder.
- Import into the active document:
  - clean hierarchy, parts parented through the asset's physics joints, axes on the joints;
  - controls for moving parts (rotate or slide within the joint's limits);
  - scale baked into the geometry, Area Weighted Phong normals, colliders hidden, one layer per asset;
  - one-mesh models split into one object per material (only when the parts of different materials share no points);
  - materials for Redshift, Standard, Arnold and V-Ray, OpenPBR where the renderer has it;
  - texture repeat from USD with UV controls on the model (Auto / Custom / Off);
  - Round corners on the model for Redshift, Arnold and V-Ray (off until switched on, default radius 0.1 cm).
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

The folders keep the project's first name so earlier downloads and settings are found.

## Licenses of the assets

SimRCL only downloads assets; their authors set the licenses (most are CC BY 4.0, which requires attribution and a note of your changes). Read the Licensing guide in Settings and the License row in the details before commercial use.

## Troubleshooting

- "Python 3 was not found": install Python 3 with "Add python.exe to PATH" and run `INSTALL.bat` again.
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
