# Claude Obsidian Vault

> A [Claude Code](https://www.anthropic.com/claude-code) skill that builds a fully automated Obsidian vault — auto-MOC via Dataview, frontmatter via Templater, two-layer tags, graph-friendly structure. Plugins install themselves.

[🇬🇧 English](#english) · [🇷🇺 Русский](#русский)

---

<a name="english"></a>
## 🇬🇧 English

### What it does

Run one command in any folder — get a production-ready Obsidian knowledge base. No manual MOC files. No hand-edited frontmatter. No plugin hunting.

The skill works in two modes:

- **New vault** — empty folder → fully structured Obsidian setup with the domains you choose.
- **Rebuild** — existing vault → reorganized into the same architecture, all your notes preserved, frontmatter auto-linked.

### Why

Most Obsidian guides leave you maintaining things by hand: updating MOC link lists, adding frontmatter on every new note, manually wiring graph connections. This skill automates **all of it** — the structure derives itself from where files live and a single `up:` field that Templater fills in for you.

### Features

- 📁 **Flat domain structure** with numeric prefixes for clean sidebar sorting
- 🗺 **One auto-MOC per domain** — universal Dataview block, no hardcoded paths, doesn't break on rename
- ⚡ **Templater frontmatter automation** — `created`, `tags`, `up` filled automatically based on file location
- 🏷 **Two-layer tag system** — auto domain tag + manual cross-cutting tags (`#review-needed`, `#todo`, `#important`)
- 🕸 **Graph-friendly** — every file links to its MOC via `up:`, every MOC links to HOME, the graph becomes a connected tree
- 🔌 **Plugins install themselves** — Dataview, Templater (and optionally Spaced Repetition, Obsidian Git) downloaded directly from GitHub releases, pre-configured, enabled
- 🌐 **Bilingual** — generates content in Russian or English based on your conversation
- 🛡 **Safe rebuild** — existing folders get renamed via `mv`, files keep their links thanks to Obsidian's auto-link-update

### Installation

#### 🪄 The lazy way (recommended)

Open Claude Code and paste:

```
Install this skill for me: https://github.com/Gleb-Vlasov/obsidian-vault-skill
```

Claude will clone the repo into your `~/.claude/skills/obsidian-vault/` directory, verify the install, and confirm. Works on any OS.

#### Manual

```bash
git clone https://github.com/Gleb-Vlasov/obsidian-vault-skill ~/.claude/skills/obsidian-vault
```

On Windows:

```powershell
git clone https://github.com/Gleb-Vlasov/obsidian-vault-skill C:\Users\<YOU>\.claude\skills\obsidian-vault
```

Requirements:
- [Claude Code](https://www.anthropic.com/claude-code)
- Python 3.9+ (uses stdlib only — no `pip install` needed)
- Internet (for plugin downloads from GitHub)

### Usage

1. Open Claude Code in the folder you want as your Obsidian vault.
2. Type `/obsidian-vault` (or just ask Claude to "set up Obsidian here").
3. Answer 2–3 questions:
   - Which domain set? (preset / custom / use existing folders)
   - Optional plugins? (Spaced Repetition, Obsidian Git)
4. Wait ~10 seconds while everything builds and plugins download.
5. Open Obsidian → enable community plugins on first launch (single click) → done.

### What you get

```
your-vault/
├── HOME.md                ← dashboard with domain links + recent edits
├── README.md              ← in-vault usage guide
├── 00 System/             ← templates, tags reference, guides
├── 01 Inbox/              ← quick capture, sort weekly
├── 02 Daily/              ← daily notes
├── 10 <Domain>/           ← your content domains
│   └── (MOC) <Domain>.md  ← auto-generated map
├── ...
└── _resources/            ← attachments
```

Every note gets:
```yaml
---
created: 2026-05-09
tags:
  - <domain>
up: "[[(MOC) <Domain>]]"
---
```

…filled automatically by Templater on creation.

### After install

Open `HOME.md` in Obsidian and explore. The `README.md` inside the vault is a full usage guide.

If you want flashcards from your study notes — install **Spaced Repetition** (the skill can do this for you when asked).
If you want auto-backup — install **Obsidian Git**.

### Architecture overview

| Layer | Tool | Purpose |
|---|---|---|
| Folder structure | OS filesystem | physical "where does this go" |
| Section maps | Dataview | auto-list files in current folder, group by subfolder |
| Frontmatter | Templater | fill `up:`, `tags`, `created` based on file location |
| Graph links | Obsidian core | `up:` field becomes a real wikilink |
| Tag discovery | Dataview queries | cross-cutting tags surface via live tables |

### Plugin auto-install — how it works

The script downloads `manifest.json`, `main.js`, and `styles.css` from each plugin's `releases/latest` on GitHub via plain `urllib`. Files land in `.obsidian/plugins/<id>/`. The plugins are added to `community-plugins.json` so Obsidian enables them on launch. Dataview's `data.json` is pre-configured with `enableDataviewJs: true` so MOCs work immediately.

This is mechanically the same thing Obsidian's built-in plugin browser does — just done from the CLI.

### License

MIT — see [LICENSE](./LICENSE).

---

<a name="русский"></a>
## 🇷🇺 Русский

### Что делает

Одна команда в любой папке — и получаешь готовую базу знаний в Obsidian. Без ручного создания MOC, без правки frontmatter, без поиска плагинов в магазине.

Скилл работает в двух режимах:

- **Новое хранилище** — пустая папка → структурированная база с твоими доменами.
- **Пересборка** — существующее хранилище → реорганизация в ту же архитектуру с сохранением всех заметок и автоматической перелинковкой frontmatter.

### Зачем

Большинство гайдов по Obsidian оставляют тебя поддерживать всё руками: обновлять списки ссылок в MOC, прописывать frontmatter в каждой новой заметке, вручную связывать узлы графа. Этот скилл автоматизирует **всё** — структура выводится из расположения файла и одного поля `up:`, которое заполняет Templater.

### Возможности

- 📁 **Плоская доменная структура** с числовыми префиксами для красивой сортировки в боковой панели
- 🗺 **Один авто-MOC на домен** — универсальный Dataview-блок без захардкоженных путей, не ломается при переименовании
- ⚡ **Автозаполнение frontmatter через Templater** — `created`, `tags`, `up` ставятся сами по расположению файла
- 🏷 **Двухслойная система тегов** — автоматический доменный тег + ручные поперечные (`#review-needed`, `#todo`, `#важное`)
- 🕸 **Граф связан с самого начала** — каждый файл ссылается на свой MOC через `up:`, каждый MOC на HOME, граф становится связным деревом
- 🔌 **Плагины ставятся сами** — Dataview, Templater (опционально Spaced Repetition, Obsidian Git) скачиваются напрямую из GitHub-релизов, конфигурируются, включаются
- 🌐 **Двуязычный** — генерирует контент на русском или английском по контексту разговора
- 🛡 **Безопасная пересборка** — папки переименовываются через `mv`, ссылки в файлах сохраняются благодаря авто-обновлению ссылок Obsidian

### Установка

#### 🪄 Ленивый способ (рекомендую)

Открой Claude Code и вставь:

```
Установи мне этот скилл: https://github.com/Gleb-Vlasov/obsidian-vault-skill
```

Claude сам клонирует репозиторий в `~/.claude/skills/obsidian-vault/`, проверит установку и подтвердит. Работает на любой ОС.

#### Руками

```bash
git clone https://github.com/Gleb-Vlasov/obsidian-vault-skill ~/.claude/skills/obsidian-vault
```

На Windows:

```powershell
git clone https://github.com/Gleb-Vlasov/obsidian-vault-skill C:\Users\<TЫ>\.claude\skills\obsidian-vault
```

Требования:
- [Claude Code](https://www.anthropic.com/claude-code)
- Python 3.9+ (только стандартная библиотека — никаких `pip install`)
- Интернет (для скачивания плагинов с GitHub)

### Использование

1. Открой Claude Code в папке, которую хочешь сделать хранилищем Obsidian.
2. Введи `/obsidian-vault` (или просто попроси Claude «настрой обсидиан»).
3. Ответь на 2–3 вопроса:
   - Какой набор доменов? (готовый пресет / кастом / использовать существующие папки)
   - Опциональные плагины? (Spaced Repetition, Obsidian Git)
4. Подожди ~10 секунд, пока всё строится и плагины качаются.
5. Открой Obsidian → разреши community plugins при первом запуске (один клик) → готово.

### Что получится

```
твоё-хранилище/
├── HOME.md                ← дашборд со ссылками на домены + последние правки
├── README.md              ← гид по использованию внутри хранилища
├── 00 Система/            ← шаблоны, справочник тегов, гайды
├── 01 Inbox/              ← быстрый захват, разбираешь раз в неделю
├── 02 Daily/              ← ежедневные заметки
├── 10 <Домен>/            ← твои контентные домены
│   └── (MOC) <Домен>.md   ← автогенерируемая карта
├── ...
└── _resources/            ← вложения
```

Каждая заметка получает:
```yaml
---
created: 2026-05-09
tags:
  - <домен>
up: "[[(MOC) <Домен>]]"
---
```

…автоматически от Templater при создании.

### После установки

Открой `HOME.md` в Obsidian и иди по ссылкам. `README.md` внутри хранилища — полный гид по использованию.

Хочешь флешкарты из учебных заметок — поставь **Spaced Repetition** (скилл сделает это сам, если попросишь).
Хочешь авто-бэкап — поставь **Obsidian Git**.

### Архитектура

| Слой | Инструмент | Зачем |
|---|---|---|
| Структура папок | файловая система | физическое «куда положить» |
| Карты разделов | Dataview | автосписок файлов своей папки с группировкой по подпапкам |
| Frontmatter | Templater | заполнение `up:`, `tags`, `created` по расположению |
| Связи в графе | ядро Obsidian | поле `up:` становится реальным wikilink |
| Поиск по темам | Dataview-запросы | поперечные теги показываются живыми таблицами |

### Как работает авто-установка плагинов

Скрипт скачивает `manifest.json`, `main.js` и `styles.css` из `releases/latest` каждого плагина через `urllib`. Файлы кладутся в `.obsidian/plugins/<id>/`. Плагины добавляются в `community-plugins.json`, чтобы Obsidian включил их при запуске. У Dataview сразу прописывается `enableDataviewJs: true`, чтобы MOC заработали мгновенно.

Это ровно то же, что делает встроенный browser плагинов в Obsidian — только из CLI.

### Лицензия

MIT — см. [LICENSE](./LICENSE).

---

Made for [Obsidian](https://obsidian.md/)</sub>
