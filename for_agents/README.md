# For AI agents

- `AGENTS.md`: how SimRCL works (service API, modules, import pipeline and why each step exists) and how to port it to Blender, Houdini, 3ds Max or another program. A copy sits in the `SimRCL` folder next to the code.
- `skills/simrcl-cinema4d/SKILL.md`: a skill for agents that drive Cinema 4D through an MCP with `exec_python` (Claude, Codex and others that read SKILL.md). It uses `simready_agent.py` so search, download and import cost a few lines of text each.

Install the skill: copy the `simrcl-cinema4d` folder into your agent's skills folder (for Claude Code: `~/.claude/skills/`), or paste SKILL.md into the agent's instructions.

# Для ИИ-агентов

- `AGENTS.md`: устройство SimRCL и инструкция по переносу в другие программы (Blender, Houdini, 3ds Max).
- `skills/simrcl-cinema4d/SKILL.md`: скилл для агентов, которые управляют Cinema 4D через MCP (`exec_python`): поиск, загрузка и импорт ассетов короткими ответами, с минимальным расходом токенов. Скопируйте папку `simrcl-cinema4d` в папку скиллов агента (для Claude Code: `~/.claude/skills/`).
