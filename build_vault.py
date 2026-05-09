"""
Obsidian vault builder for the obsidian-vault skill.

Usage:
    python build_vault.py --config <path-to-config.json>

Config format:
{
  "mode": "new" | "rebuild",
  "lang": "ru" | "en",
  "vault_path": "<absolute path>",
  "domains": [
    { "prefix": "10", "name": "Учёба", "emoji": "🎓", "tag": "study", "old_path": "Учёба" }
  ],
  "install_plugins": ["dataview", "templater-obsidian"]
}

`old_path` is optional; only used in rebuild mode for renaming existing folders.
`install_plugins` is optional; defaults to dataview + templater-obsidian.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# I18N STRINGS
# ─────────────────────────────────────────────────────────────────────────────

I18N: dict[str, dict[str, str]] = {
    "ru": {
        "system_folder": "00 Система",
        "inbox_folder": "01 Inbox",
        "daily_folder": "02 Daily",
        "templates_folder": "Templates",
        "guides_folder": "Guides",
        "obsidian_folder": "Obsidian",
        "system_moc": "(MOC) Система",
        "inbox_moc": "(MOC) Inbox",
        "daily_moc": "(MOC) Daily",
        "tags_file": "Теги",
        "in_root_section": "📄 В корне раздела",
        "moc_subtitle": "Карта раздела. Файлы группируются автоматически по подпапкам. Возврат:",
    },
    "en": {
        "system_folder": "00 System",
        "inbox_folder": "01 Inbox",
        "daily_folder": "02 Daily",
        "templates_folder": "Templates",
        "guides_folder": "Guides",
        "obsidian_folder": "Obsidian",
        "system_moc": "(MOC) System",
        "inbox_moc": "(MOC) Inbox",
        "daily_moc": "(MOC) Daily",
        "tags_file": "Tags",
        "in_root_section": "📄 In section root",
        "moc_subtitle": "Section map. Files are grouped automatically by subfolder. Back to:",
    },
}

PROTECTED_DIRS = {".obsidian", ".trash", "_resources", "files"}

# ─────────────────────────────────────────────────────────────────────────────
# CONTENT TEMPLATES (Dataview-driven, parameterized by language)
# ─────────────────────────────────────────────────────────────────────────────

DATAVIEWJS_MOC = '''```dataviewjs
const here = dv.current().file.folder;
const me = dv.current().file.path;
const pages = dv.pages(`"${here}"`).where(p => p.file.path !== me);

const groups = new Map();
for (const p of pages) {
  let rel = p.file.folder.substring(here.length).replace(/^\\//, "");
  const top = rel === "" ? "%IN_ROOT%" : rel.split("/")[0];
  if (!groups.has(top)) groups.set(top, []);
  groups.get(top).push(p);
}

for (const [name, items] of [...groups.entries()].sort()) {
  dv.header(2, name);
  dv.list(
    items.sort((a, b) => a.file.name.localeCompare(b.file.name))
         .map(p => p.file.link)
  );
}
```'''


def domain_moc_content(domain: dict, lang: str) -> str:
    s = I18N[lang]
    block = DATAVIEWJS_MOC.replace("%IN_ROOT%", s["in_root_section"])
    return f"""---
tags:
  - moc
  - {domain['tag']}
created: {iso_today()}
up: "[[HOME]]"
---

# {domain['emoji']} {domain['name']}

> {s['moc_subtitle']} [[HOME]]

---

{block}
"""


def system_moc_content(lang: str) -> str:
    s = I18N[lang]
    block = DATAVIEWJS_MOC.replace("%IN_ROOT%", s["in_root_section"])
    title = "🧰 Система" if lang == "ru" else "🧰 System"
    return f"""---
tags:
  - moc
  - system
created: {iso_today()}
up: "[[HOME]]"
---

# {title}

> {s['moc_subtitle']} [[HOME]]

---

{block}
"""


def inbox_moc_content(lang: str) -> str:
    s = I18N[lang]
    block = DATAVIEWJS_MOC.replace("%IN_ROOT%", s["in_root_section"])
    if lang == "ru":
        title = "📥 Inbox"
        sub = ("Сюда складываешь всё, что пришло в голову, но пока непонятно куда деть. "
               "Раз в неделю разбираешь — переносишь в нужный домен. Возврат: [[HOME]]")
    else:
        title = "📥 Inbox"
        sub = ("Capture anything here when you don't know where it belongs. "
               "Sort weekly — move into the right domain. Back to: [[HOME]]")
    return f"""---
tags:
  - moc
  - inbox
created: {iso_today()}
up: "[[HOME]]"
---

# {title}

> {sub}

---

{block}
"""


def daily_moc_content(lang: str) -> str:
    s = I18N[lang]
    block = DATAVIEWJS_MOC.replace("%IN_ROOT%", s["in_root_section"])
    title = "📅 Daily"
    sub = "Ежедневные заметки. Возврат: [[HOME]]" if lang == "ru" else "Daily notes. Back to: [[HOME]]"
    return f"""---
tags:
  - moc
  - daily
created: {iso_today()}
up: "[[HOME]]"
---

# {title}

> {sub}

---

{block}
"""


def home_content(domains: list[dict], lang: str) -> str:
    s = I18N[lang]
    if lang == "ru":
        title = "# 🏠 Главная"
        intro = ("> Центральная точка входа. Каждый домен — отдельная карта (MOC). "
                 "Создаёшь файл в правильной папке — он сам появляется в нужной карте.")
        h_domains = "## 🗺 Домены"
        h_system = "## 🛠 Системное"
        h_recent = "## 🔥 Последние правки"
        col_domain, col_map = "Домен", "Карта"
        sys_inbox = f"📥 [[{s['inbox_moc']}]] — быстрый захват, потом разбираешь"
        sys_daily = f"📅 [[{s['daily_moc']}]] — ежедневные заметки"
        sys_sys = f"🧰 [[{s['system_moc']}]] — шаблоны, гайды, обсидиан"
        col_file, col_folder, col_mtime = "Файл", "Папка", "Изменён"
    else:
        title = "# 🏠 Home"
        intro = ("> Central entry point. Each domain has its own map (MOC). "
                 "Drop a file into the right folder — it appears in the corresponding MOC automatically.")
        h_domains = "## 🗺 Domains"
        h_system = "## 🛠 System"
        h_recent = "## 🔥 Recent edits"
        col_domain, col_map = "Domain", "Map"
        sys_inbox = f"📥 [[{s['inbox_moc']}]] — quick capture, sort later"
        sys_daily = f"📅 [[{s['daily_moc']}]] — daily notes"
        sys_sys = f"🧰 [[{s['system_moc']}]] — templates, guides, Obsidian setup"
        col_file, col_folder, col_mtime = "File", "Folder", "Modified"

    rows = "\n".join(
        f"| {d['emoji']} {d['name']} | [[(MOC) {d['name']}]] |" for d in domains
    )

    return f"""---
tags:
  - moc
  - home
created: {iso_today()}
---

{title}

{intro}

---

{h_domains}

| {col_domain} | {col_map} |
| --- | --- |
{rows}

---

{h_system}

- {sys_inbox}
- {sys_daily}
- {sys_sys}

---

{h_recent}

```dataviewjs
const skip = ["_resources", "files", ".obsidian", ".trash"];
dv.table(
  ["{col_file}", "{col_folder}", "{col_mtime}"],
  dv.pages('""')
    .where(p =>
      p.file.path !== dv.current().file.path &&
      !skip.some(s => p.file.path.startsWith(s))
    )
    .sort(p => p.file.mtime, "desc")
    .limit(15)
    .map(p => [p.file.link, p.file.folder, p.file.mtime])
);
```
"""


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATER TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────


def default_template(domains: list[dict], system_folder: str, inbox_folder: str,
                     daily_folder: str) -> str:
    """Templater template that auto-fills frontmatter based on file location."""
    folder_map_entries = []
    for d in domains:
        folder_name = f"{d['prefix']} {d['name']}"
        folder_map_entries.append(
            f'  "{folder_name}": {{ moc: "(MOC) {d["name"]}", tag: "{d["tag"]}" }},'
        )
    folder_map_entries.append(
        f'  "{system_folder}": {{ moc: "(MOC) {system_folder.split(" ", 1)[1] if " " in system_folder else system_folder}", tag: "system" }},'
    )
    folder_map_entries.append(
        f'  "{inbox_folder}": {{ moc: "(MOC) Inbox", tag: "inbox" }},'
    )
    folder_map_entries.append(
        f'  "{daily_folder}": {{ moc: "(MOC) Daily", tag: "daily" }},'
    )
    folder_map_str = "\n".join(folder_map_entries)

    return f"""<%*
const folderMap = {{
{folder_map_str}
}};
const folder = tp.file.folder(true) || "";
const top = folder.split("/")[0];
const info = folderMap[top] || {{ moc: "", tag: "" }};
-%>
---
created: <% tp.date.now("YYYY-MM-DD") %>
tags:
  - <% info.tag %>
up: "[[<% info.moc %>]]"
---

"""


def main_template(domains: list[dict], system_folder: str, inbox_folder: str,
                  daily_folder: str, lang: str) -> str:
    folder_map_entries = []
    for d in domains:
        folder_name = f"{d['prefix']} {d['name']}"
        folder_map_entries.append(
            f'  "{folder_name}": {{ moc: "(MOC) {d["name"]}", tag: "{d["tag"]}" }},'
        )
    folder_map_str = "\n".join(folder_map_entries)
    if lang == "ru":
        sections = "# Аннотация\n\n\n---\n\n# Main\n\n\n---\n\n# Источники\n\n\n---\n\n# Заключение\n"
    else:
        sections = "# Abstract\n\n\n---\n\n# Main\n\n\n---\n\n# Sources\n\n\n---\n\n# Conclusion\n"

    return f"""<%*
const folderMap = {{
{folder_map_str}
}};
const folder = tp.file.folder(true) || "";
const top = folder.split("/")[0];
const info = folderMap[top] || {{ moc: "", tag: "" }};
-%>
---
created: <% tp.date.now("YYYY-MM-DD") %>
tags:
  - <% info.tag %>
up: "[[<% info.moc %>]]"
sources:
---

{sections}"""


def daily_template(lang: str) -> str:
    if lang == "ru":
        return """---
created: "<% tp.date.now('YYYY-MM-DD') %>"
tags:
  - daily
up: "[[(MOC) Daily]]"
---

### Краткое описание


### Что сделал


### Что узнал
"""
    return """---
created: "<% tp.date.now('YYYY-MM-DD') %>"
tags:
  - daily
up: "[[(MOC) Daily]]"
---

### Summary


### Done today


### Learned
"""


def moc_template(lang: str) -> str:
    title = "{{title}}" if True else None
    s = I18N[lang]
    block = DATAVIEWJS_MOC.replace("%IN_ROOT%", s["in_root_section"])
    sub = "Карта раздела. Возврат: [[HOME]]" if lang == "ru" else "Section map. Back to: [[HOME]]"
    return f"""---
tags:
  - moc
created: "<% tp.date.now('YYYY-MM-DD') %>"
up: "[[HOME]]"
---

# {{{{title}}}}

> {sub}

---

{block}
"""


# ─────────────────────────────────────────────────────────────────────────────
# TAGS GUIDE FILE
# ─────────────────────────────────────────────────────────────────────────────


def tags_guide(domains: list[dict], lang: str) -> str:
    rows = "\n".join(f"| `#{d['tag']}` | {d['emoji']} {d['name']} |" for d in domains)
    if lang == "ru":
        return f"""---
created: {iso_today()}
tags:
  - system
  - moc
up: "[[(MOC) Система]]"
---

# 🏷 Справочник тегов

> Папка отвечает «куда положить». Тег — «о чём это». Если хочешь добавить новый поперечный тег — впиши в этот файл и используй.

---

## 🔵 Доменные теги (ставит Templater автоматически)

| Тег | Домен |
|---|---|
{rows}
| `#system` | Системные файлы |
| `#inbox` | Inbox |
| `#daily` | Daily-заметки |

Эти теги дублируют папку — но удобны для фильтров в графе и Dataview.

---

## 🟢 Поперечные теги — содержание

Связывают файлы из разных доменов одной темой. Примеры:

| Тег | Когда ставить |
|---|---|
| `#проект-X` | Замени X на код проекта. Все файлы по проекту. |
| `#tool-X` | Заметки про конкретный инструмент. |

---

## 🟡 Поперечные теги — статус и процесс

| Тег | Когда ставить |
|---|---|
| `#fleeting` | Черновая мысль, требует доработки. |
| `#review-needed` | Нужно перечитать и доработать. |
| `#важное` | Маркер для быстрого поиска. |
| `#todo` | Внутри есть пункт для выполнения. |
| `#archive` | Неактуально, но не удалять. |

---

## 📊 Живые подборки

### Требует доработки
```dataview
LIST
FROM #review-needed OR #todo
SORT file.mtime DESC
```

### Inbox для разбора
```dataview
LIST
FROM #fleeting
SORT file.mtime DESC
```

---

## 💡 Принципы

1. **Доменный тег ставится автоматически** — про него не думай.
2. **Поперечный тег ставь только если он реально пересекает границу папки.**
3. **Не плоди теги бесконтрольно.** Лишние теги засоряют граф.
4. **Статусные теги удаляй после выполнения.**
"""
    # English
    return f"""---
created: {iso_today()}
tags:
  - system
  - moc
up: "[[(MOC) System]]"
---

# 🏷 Tags Guide

> Folders answer "where does this go". Tags answer "what's it about". If you want to add a new cross-cutting tag — list it here and use it.

---

## 🔵 Domain tags (auto-set by Templater)

| Tag | Domain |
|---|---|
{rows}
| `#system` | System files |
| `#inbox` | Inbox |
| `#daily` | Daily notes |

These duplicate the folder, but help with graph filters and Dataview queries.

---

## 🟢 Cross-cutting tags — by topic

Link files across domains. Examples:

| Tag | When to apply |
|---|---|
| `#project-X` | All files for project X. |
| `#tool-X` | Notes about a specific tool. |

---

## 🟡 Cross-cutting tags — status and process

| Tag | When to apply |
|---|---|
| `#fleeting` | Rough thought, needs refining. |
| `#review-needed` | Needs revisiting. |
| `#important` | Fast-find marker. |
| `#todo` | Contains action items. |
| `#archive` | Outdated but kept. |

---

## 📊 Live queries

### Needs work
```dataview
LIST
FROM #review-needed OR #todo
SORT file.mtime DESC
```

### Inbox to sort
```dataview
LIST
FROM #fleeting
SORT file.mtime DESC
```

---

## 💡 Principles

1. **Domain tag is automatic** — don't think about it.
2. **Add cross-cutting tag only when it crosses folder boundaries.**
3. **Don't proliferate tags.** Excess tags pollute the graph.
4. **Remove status tags once resolved.**
"""


# ─────────────────────────────────────────────────────────────────────────────
# README — full guide
# ─────────────────────────────────────────────────────────────────────────────


def readme(domains: list[dict], system_folder: str, inbox_folder: str,
           daily_folder: str, lang: str) -> str:
    domain_lines = "\n".join(
        f"├── {d['prefix']} {d['name']}/" for d in domains
    )
    if lang == "ru":
        return f"""# 📚 База знаний — полное руководство

Точка входа — [[HOME]]. Этот файл — справочник по системе.

---

## TL;DR за 30 секунд

- Файл в правильной папке → автоматически в карте раздела (MOC) и графе.
- Frontmatter заполняется Templater при создании.
- Не знаешь куда → `{inbox_folder}/`, разбираешь раз в неделю.
- Сквозные подборки → поперечные теги (`#review-needed`, `#важное`).
- Главная панель — `HOME.md`.

---

## Главная идея

**Один источник правды.** Структура выводится из физического расположения файла + полей frontmatter (`tags`, `up`, `created`). Никаких ручных списков.

### Три слоя организации

| Слой | Кто отвечает | Зачем |
|---|---|---|
| Папка | физическая структура | основная классификация |
| Доменный тег | автомат при создании | для фильтров и графа |
| Поперечный тег | руками когда осмысленно | связь между доменами |

---

## Структура папок

```
{system_folder}/      ← инфраструктура (шаблоны, гайды, теги)
{inbox_folder}/       ← быстрый захват
{daily_folder}/       ← ежедневные заметки
{domain_lines}
_resources/      ← вложения и картинки
```

Префиксы — для сортировки в боковой панели. `00` системное наверху, `10+` — домены.

---

## Плагины

### Обязательные

- **Dataview** — превращает MOC в живые автосписки.
- **Templater** — автозаполнение frontmatter.

### Опциональные

- **Spaced Repetition** — флешкарты из заметок (для учебных доменов).
- **Obsidian Git** — авто-бэкап в GitHub.

### Установка

Settings (Ctrl+,) → Community plugins → (если первый раз) включи Community plugins → Browse → найди плагин → Install → Enable.

---

## Повседневные сценарии

### Создать заметку
Правой кнопкой по подпапке → New note. Templater сам впишет frontmatter.

### Возникла мысль, не знаю куда
Правой кнопкой по `{inbox_folder}/` → New note. На разборе раз в неделю переносишь.

### Перенести из Inbox в домен
Перетащи файл. **Frontmatter обнови руками** (или команда `Templater: Replace templates in active file`) — Templater при перетаскивании не срабатывает.

### Найти связанное по теме
Через теги в `{system_folder}/Теги.md` или просто введи `#tag` в поиске.

---

## MOC — как работает

В каждом MOC лежит универсальный `dataviewjs`-блок. Он берёт свою папку через `dv.current().file.folder` и листит всё внутри, группируя по подпапкам. Путь нигде не зашит — переименование папок ничего не ломает.

Подпапкам собственный MOC **не нужен** — Dataview оформит их как разделы автоматически.

---

## Frontmatter

```yaml
---
created: 2026-05-09
tags:
  - <домен>
  - <поперечный тег по желанию>
up: "[[(MOC) Домен]]"
---
```

`up:` создаёт реальную графовую связь. Templater заполняет всё это сам.

---

## Граф

Звёздная структура: HOME ← MOC ← файлы. В настройках графа полезно:
- Filters → Tags: вкл — теги станут хабами.
- Groups: покрась домены по `path:`-фильтру.

---

## Переименование

| Что | Делать руками? |
|---|---|
| Папку | ❌ MOC сам подхватит |
| MOC | ❌ Obsidian обновит `up:` |
| Заметку | ❌ wikilinks обновятся |
| Перенос заметки в другую папку | ⚠️ frontmatter обнови сам |

Только через Obsidian — НЕ через проводник Windows.

---

## Еженедельный ритуал (15 минут)

1. Разобрать Inbox.
2. Проверить `#review-needed` и `#todo`.
3. Просмотреть последние правки в HOME.
4. (Если стоит SR) — пройти очередь повторений.

---

## Чего НЕ делать

- Не дроби длинные заметки на «атомарные».
- Не добавляй поля во frontmatter.
- Не реорганизуй папки — текущая хороша.
- Не плоди MOC в подпапках.
- Не ставь больше плагинов.

---

Полный гид с подробностями (troubleshooting, добавление нового домена и т.д.) — был сгенерирован при первой сборке. Если хочешь дополнить — открой и редактируй.
"""
    # English
    return f"""# 📚 Knowledge base — full guide

Entry point — [[HOME]]. This file documents the system.

---

## TL;DR in 30 seconds

- File in the right folder → automatically in section map (MOC) and graph.
- Frontmatter auto-filled by Templater on creation.
- Don't know where → `{inbox_folder}/`, sort weekly.
- Cross-cutting collections → cross-cutting tags (`#review-needed`, `#important`).
- Main dashboard — `HOME.md`.

---

## Core idea

**Single source of truth.** Structure is derived from file location + frontmatter (`tags`, `up`, `created`). No manual lists.

### Three layers

| Layer | Who controls | Purpose |
|---|---|---|
| Folder | physical structure | primary classification |
| Domain tag | auto on creation | graph filters, Dataview |
| Cross-cutting tag | manually when meaningful | links across domains |

---

## Folder structure

```
{system_folder}/     ← infrastructure (templates, guides, tags)
{inbox_folder}/      ← quick capture
{daily_folder}/      ← daily notes
{domain_lines}
_resources/    ← attachments
```

Numeric prefixes sort the sidebar. `00` for system at top, `10+` for content.

---

## Plugins

### Required

- **Dataview** — turns MOCs into live auto-lists.
- **Templater** — auto-fills frontmatter.

### Optional

- **Spaced Repetition** — flashcards from notes.
- **Obsidian Git** — automatic backup to GitHub.

### Install

Settings (Ctrl+,) → Community plugins → (if first time) turn on Community plugins → Browse → find plugin → Install → Enable.

---

## Workflows

### New note
Right-click target subfolder → New note. Templater fills the frontmatter.

### Random thought, don't know where
Right-click `{inbox_folder}/` → New note. Sort weekly.

### Move from Inbox to a domain
Drag the file. **Update frontmatter manually** (or run `Templater: Replace templates in active file`) — Templater doesn't run on moves.

### Find by topic
Use tags in `{system_folder}/Tags.md` or type `#tag` in search.

---

## MOC — how it works

Each MOC contains a universal `dataviewjs` block. It uses `dv.current().file.folder` to know its own folder and lists everything inside, grouped by subfolder. No paths are hardcoded — renaming folders does not break anything.

Subfolders **don't need** their own MOC — Dataview groups them as sections automatically.

---

## Frontmatter

```yaml
---
created: 2026-05-09
tags:
  - <domain>
  - <optional cross-cutting tag>
up: "[[(MOC) Domain]]"
---
```

`up:` creates a real graph link. Templater fills all this in for you.

---

## Graph

Star pattern: HOME ← MOC ← notes. Useful graph settings:
- Filters → Tags: on — tags become hubs.
- Groups: color domains by `path:` filter.

---

## Renaming

| What | Manual? |
|---|---|
| Folder | ❌ MOC adapts |
| MOC | ❌ Obsidian updates `up:` |
| Note | ❌ wikilinks updated |
| Moving note across folders | ⚠️ update frontmatter |

Always through Obsidian — NOT via OS file manager.

---

## Weekly ritual (15 min)

1. Sort Inbox.
2. Check `#review-needed` and `#todo`.
3. Skim Recent edits on HOME.
4. (If SR installed) — run review queue.

---

## What NOT to do

- Don't atomize long notes Zettelkasten-style.
- Don't add new frontmatter fields.
- Don't reorganize folders — the current is fine.
- Don't add MOCs to subfolders.
- Don't install more plugins.

---

A deeper version of this guide can be expanded inside the vault as you learn what's worth documenting.
"""


# ─────────────────────────────────────────────────────────────────────────────
# OBSIDIAN CONFIG FILES
# ─────────────────────────────────────────────────────────────────────────────


def obsidian_app_json() -> dict:
    return {
        "alwaysUpdateLinks": True,
        "attachmentFolderPath": "_resources/images",
        "defaultViewMode": "preview",
        "promptDelete": False,
    }


def obsidian_templates_json(system_folder: str) -> dict:
    return {
        "folder": f"{system_folder}/Templates",
        "dateFormat": "YYYY-MM-DD",
    }


def obsidian_daily_notes_json(system_folder: str, daily_folder: str) -> dict:
    return {
        "format": "YYYY-MM-DD",
        "folder": daily_folder,
        "template": f"{system_folder}/Templates/Daily Template",
    }


def obsidian_community_plugins() -> list[str]:
    return ["dataview", "templater-obsidian"]


def templater_data_json(domains: list[dict], system_folder: str,
                        inbox_folder: str) -> dict:
    folder_templates = [
        {"folder": inbox_folder, "template": f"{system_folder}/Templates/Default Template.md"},
    ]
    for d in domains:
        folder_templates.append({
            "folder": f"{d['prefix']} {d['name']}",
            "template": f"{system_folder}/Templates/Default Template.md",
        })
    folder_templates.append({
        "folder": f"{system_folder}/Guides",
        "template": f"{system_folder}/Templates/Default Template.md",
    })
    folder_templates.append({
        "folder": f"{system_folder}/Obsidian",
        "template": f"{system_folder}/Templates/Default Template.md",
    })
    return {
        "command_timeout": 5,
        "templates_folder": f"{system_folder}/Templates",
        "templates_pairs": [["", ""]],
        "trigger_on_file_creation": True,
        "auto_jump_to_cursor": False,
        "enable_system_commands": False,
        "shell_path": "",
        "user_scripts_folder": "",
        "enable_folder_templates": True,
        "folder_templates": folder_templates,
        "syntax_highlighting": True,
        "syntax_highlighting_mobile": False,
        "enabled_templates_hotkeys": [""],
        "startup_templates": [""],
    }


# ─────────────────────────────────────────────────────────────────────────────
# FRONTMATTER UTILS
# ─────────────────────────────────────────────────────────────────────────────


def iso_today() -> str:
    from datetime import date
    return date.today().isoformat()


def parse_frontmatter(text: str) -> tuple[list[str] | None, str]:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[4:end].splitlines(), text[end + 5:]
    if text.startswith("---\r\n"):
        end = text.find("\r\n---\r\n", 5)
        if end != -1:
            return text[5:end].splitlines(), text[end + 7:]
    return None, text


def has_field(fm_lines: list[str], name: str) -> bool:
    return any(re.match(rf"^{name}\s*:", line) for line in fm_lines)


def set_field(fm_lines: list[str], name: str, value: str) -> list[str]:
    pattern = re.compile(rf"^{name}\s*:")
    new_lines: list[str] = []
    replaced = False
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        if not replaced and pattern.match(line):
            new_lines.append(f"{name}: {value}")
            replaced = True
            i += 1
            while i < len(fm_lines) and (fm_lines[i].startswith(" ")
                                          or fm_lines[i].startswith("\t")
                                          or fm_lines[i].startswith("-")):
                i += 1
            continue
        new_lines.append(line)
        i += 1
    if not replaced:
        new_lines.append(f"{name}: {value}")
    return new_lines


def ensure_tag(fm_lines: list[str], tag: str) -> list[str]:
    out: list[str] = []
    i = 0
    found = False
    while i < len(fm_lines):
        line = fm_lines[i]
        if not found and re.match(r"^tags\s*:", line):
            found = True
            existing: list[str] = []
            inline = line.split(":", 1)[1].strip()
            if inline:
                if inline.startswith("["):
                    existing = [t.strip().strip('"').strip("'")
                                for t in inline.strip("[]").split(",") if t.strip()]
                else:
                    existing = [inline.strip().strip('"').strip("'")]
                i += 1
            else:
                i += 1
                while i < len(fm_lines) and (fm_lines[i].startswith("  -")
                                              or fm_lines[i].startswith("- ")
                                              or fm_lines[i].startswith("\t-")):
                    item = fm_lines[i].lstrip(" \t-").strip().strip('"').strip("'")
                    if item:
                        existing.append(item)
                    i += 1
            if tag and tag not in existing:
                existing.append(tag)
            out.append("tags:")
            for t in existing:
                out.append(f"  - {t}")
            continue
        out.append(line)
        i += 1
    if not found and tag:
        out.append("tags:")
        out.append(f"  - {tag}")
    return out


def add_up_and_tag(file_path: Path, moc_name: str, tag: str) -> bool:
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return False
    fm, body = parse_frontmatter(text)
    if fm is None:
        fm = []
        body = text
    fm = set_field(fm, "up", f'"[[{moc_name}]]"')
    fm = ensure_tag(fm, tag)
    new_text = "---\n" + "\n".join(fm) + "\n---\n" + body
    if new_text != text:
        file_path.write_text(new_text, encoding="utf-8")
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BUILDER
# ─────────────────────────────────────────────────────────────────────────────


def is_moc_file(name: str) -> bool:
    # Catch (MOC), (МOC), (МОС) variants
    return name.startswith("(MOC)") or name.startswith("(М") and "OC" in name[:6] or name.startswith("(МО")


def delete_old_mocs(vault: Path) -> int:
    count = 0
    for p in vault.rglob("*.md"):
        if any(part in PROTECTED_DIRS for part in p.parts):
            continue
        if is_moc_file(p.name):
            try:
                p.unlink()
                count += 1
            except Exception:
                pass
    return count


def safe_move(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if src.resolve() == dst.resolve():
        return
    if dst.exists():
        # merge: move children
        for child in list(src.iterdir()):
            target = dst / child.name
            if target.exists():
                # nested merge for dirs, skip for files
                if child.is_dir() and target.is_dir():
                    safe_move(child, target)
                else:
                    print(f"  ! skipped (exists): {target}")
            else:
                shutil.move(str(child), str(target))
        try:
            src.rmdir()
        except OSError:
            pass
    else:
        shutil.move(str(src), str(dst))


def build(config: dict) -> dict:
    vault = Path(config["vault_path"]).resolve()
    lang = config.get("lang", "ru")
    mode = config["mode"]
    domains = config["domains"]
    s = I18N[lang]

    summary: dict[str, Any] = {
        "vault": str(vault),
        "mode": mode,
        "lang": lang,
        "domains": [f"{d['prefix']} {d['name']}" for d in domains],
        "actions": [],
    }

    if not vault.exists():
        vault.mkdir(parents=True)
        summary["actions"].append(f"created vault dir: {vault}")

    # ── 1. Rename existing folders for rebuild
    if mode == "rebuild":
        for d in domains:
            old = d.get("old_path")
            new_name = f"{d['prefix']} {d['name']}"
            new_path = vault / new_name
            if old and (vault / old).exists() and old != new_name:
                safe_move(vault / old, new_path)
                summary["actions"].append(f"moved: {old} → {new_name}")
            elif not new_path.exists():
                new_path.mkdir(parents=True)
                summary["actions"].append(f"created: {new_name}")

        # Delete all old MOC files anywhere
        deleted = delete_old_mocs(vault)
        if deleted:
            summary["actions"].append(f"deleted {deleted} old MOC files")

    # ── 2. Ensure standard structure
    sys_folder = vault / s["system_folder"]
    inbox_folder = vault / s["inbox_folder"]
    daily_folder = vault / s["daily_folder"]
    for f in (sys_folder, inbox_folder, daily_folder,
              sys_folder / "Templates",
              sys_folder / "Guides",
              sys_folder / "Obsidian"):
        f.mkdir(parents=True, exist_ok=True)

    for d in domains:
        (vault / f"{d['prefix']} {d['name']}").mkdir(exist_ok=True)

    # ── 3. Write all MOCs
    for d in domains:
        moc_path = vault / f"{d['prefix']} {d['name']}" / f"(MOC) {d['name']}.md"
        moc_path.write_text(domain_moc_content(d, lang), encoding="utf-8")
        summary["actions"].append(f"wrote MOC: {moc_path.name}")

    (sys_folder / f"{s['system_moc']}.md").write_text(system_moc_content(lang), encoding="utf-8")
    (inbox_folder / f"{s['inbox_moc']}.md").write_text(inbox_moc_content(lang), encoding="utf-8")
    (daily_folder / f"{s['daily_moc']}.md").write_text(daily_moc_content(lang), encoding="utf-8")

    # ── 4. Templates
    tpls = sys_folder / "Templates"
    (tpls / "Default Template.md").write_text(
        default_template(domains, s["system_folder"], s["inbox_folder"], s["daily_folder"]),
        encoding="utf-8",
    )
    (tpls / "Main Template.md").write_text(
        main_template(domains, s["system_folder"], s["inbox_folder"], s["daily_folder"], lang),
        encoding="utf-8",
    )
    (tpls / "Daily Template.md").write_text(daily_template(lang), encoding="utf-8")
    (tpls / "MOC Template.md").write_text(moc_template(lang), encoding="utf-8")

    # ── 5. Tags guide
    (sys_folder / f"{s['tags_file']}.md").write_text(tags_guide(domains, lang), encoding="utf-8")

    # ── 6. HOME and README
    (vault / "HOME.md").write_text(home_content(domains, lang), encoding="utf-8")
    (vault / "README.md").write_text(
        readme(domains, s["system_folder"], s["inbox_folder"], s["daily_folder"], lang),
        encoding="utf-8",
    )

    # ── 7. Obsidian config
    obs = vault / ".obsidian"
    obs.mkdir(exist_ok=True)
    (obs / "app.json").write_text(json.dumps(obsidian_app_json(), indent=2, ensure_ascii=False),
                                  encoding="utf-8")
    (obs / "templates.json").write_text(
        json.dumps(obsidian_templates_json(s["system_folder"]), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (obs / "daily-notes.json").write_text(
        json.dumps(obsidian_daily_notes_json(s["system_folder"], s["daily_folder"]),
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # community plugins — merge with existing
    plugins_to_install = config.get("install_plugins")
    if plugins_to_install is None:
        plugins_to_install = ["dataview", "templater-obsidian"]

    cp_path = obs / "community-plugins.json"
    if cp_path.exists():
        try:
            existing = json.loads(cp_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    else:
        existing = []
    for p in plugins_to_install:
        if p not in existing:
            existing.append(p)
    cp_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    # auto-download plugins
    print(f"\nDownloading plugins from GitHub...")
    install_results = install_all_plugins(vault, plugins_to_install)
    summary["plugins_installed"] = install_results
    failed_plugins = [pid for pid, msg in install_results.items() if not msg.startswith("✓")]
    if failed_plugins:
        summary["actions"].append(
            f"⚠ failed to install: {', '.join(failed_plugins)} — install manually via Settings"
        )
    else:
        summary["actions"].append(
            f"installed {len(install_results)} plugins: {', '.join(install_results.keys())}"
        )

    # Templater config
    tpl_dir = obs / "plugins" / "templater-obsidian"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    (tpl_dir / "data.json").write_text(
        json.dumps(templater_data_json(domains, s["system_folder"], s["inbox_folder"]),
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Dataview config — enable JS queries (off by default for security)
    dv_dir = obs / "plugins" / "dataview"
    dv_dir.mkdir(parents=True, exist_ok=True)
    dv_data_path = dv_dir / "data.json"
    if dv_data_path.exists():
        try:
            dv_existing = json.loads(dv_data_path.read_text(encoding="utf-8"))
        except Exception:
            dv_existing = {}
    else:
        dv_existing = {}
    dv_existing["enableDataviewJs"] = True
    dv_existing["enableInlineDataviewJs"] = True
    dv_data_path.write_text(
        json.dumps(dv_existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ── 8. Add `up:` and tag to all existing files in each domain
    domain_map: dict[str, tuple[str, str]] = {}
    for d in domains:
        domain_map[f"{d['prefix']} {d['name']}"] = (f"(MOC) {d['name']}", d["tag"])
    domain_map[s["system_folder"]] = (s["system_moc"], "system")
    domain_map[s["inbox_folder"]] = (s["inbox_moc"], "inbox")
    domain_map[s["daily_folder"]] = (s["daily_moc"], "daily")

    updated = 0
    for top_name, (moc_name, tag) in domain_map.items():
        root = vault / top_name
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            if any(part in PROTECTED_DIRS for part in p.parts):
                continue
            if is_moc_file(p.name):
                continue
            if "Template" in p.name and p.parent.name == "Templates":
                continue
            if add_up_and_tag(p, moc_name, tag):
                updated += 1
    summary["files_relinked"] = updated
    summary["actions"].append(f"added up: and tag to {updated} files")

    return summary


# ─────────────────────────────────────────────────────────────────────────────
# PLUGIN INSTALLER
# ─────────────────────────────────────────────────────────────────────────────

PLUGIN_REPOS: dict[str, str] = {
    "dataview":                   "blacksmithgu/obsidian-dataview",
    "templater-obsidian":         "SilentVoid13/Templater",
    "obsidian-spaced-repetition": "st3v3nmw/obsidian-spaced-repetition",
    "obsidian-git":               "Vinzent03/obsidian-git",
    "calendar":                   "liamcain/obsidian-calendar-plugin",
    "obsidian-excalidraw-plugin": "zsviczian/obsidian-excalidraw-plugin",
}


def _download(url: str, timeout: int = 30) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "obsidian-vault-skill"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None


def install_plugin(vault: Path, plugin_id: str) -> tuple[bool, str]:
    """Download a plugin's release files from GitHub and place them in .obsidian/plugins/<id>/.

    Returns (success, message).
    """
    repo = PLUGIN_REPOS.get(plugin_id)
    if not repo:
        return False, f"unknown plugin id: {plugin_id}"
    plugin_dir = vault / ".obsidian" / "plugins" / plugin_id
    plugin_dir.mkdir(parents=True, exist_ok=True)
    base = f"https://github.com/{repo}/releases/latest/download"
    required = ("manifest.json", "main.js")
    optional = ("styles.css",)

    for fname in required:
        data = _download(f"{base}/{fname}")
        if data is None:
            return False, f"failed to download required file: {fname}"
        (plugin_dir / fname).write_bytes(data)

    for fname in optional:
        data = _download(f"{base}/{fname}")
        if data is not None:
            (plugin_dir / fname).write_bytes(data)

    return True, "ok"


def install_all_plugins(vault: Path, plugin_ids: list[str]) -> dict[str, str]:
    """Install all listed plugins. Returns {plugin_id: status_message}."""
    results: dict[str, str] = {}
    for pid in plugin_ids:
        ok, msg = install_plugin(vault, pid)
        results[pid] = "✓ installed" if ok else f"✗ {msg}"
        print(f"  plugin {pid}: {results[pid]}")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build/rebuild an Obsidian vault.")
    parser.add_argument("--config", required=True, help="Path to JSON config")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))

    summary = build(config)

    print("\n=== BUILD SUMMARY ===")
    print(f"Vault:    {summary['vault']}")
    print(f"Mode:     {summary['mode']}")
    print(f"Lang:     {summary['lang']}")
    print(f"Domains:  {', '.join(summary['domains'])}")
    print(f"Files relinked: {summary.get('files_relinked', 0)}")
    print("\nActions:")
    for a in summary["actions"]:
        print(f"  • {a}")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
