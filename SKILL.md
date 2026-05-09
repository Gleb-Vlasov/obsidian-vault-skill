---
name: obsidian-vault
description: Set up or rebuild an Obsidian vault with auto-MOC (Dataview), Templater-based frontmatter automation, two-layer tags, and graph-friendly structure. Use when the user asks to "set up Obsidian", "organize my vault", "create Obsidian knowledge base", "rebuild Obsidian", or invokes /obsidian-vault. Works on both empty folders (creates fresh vault) and existing vaults (rebuilds them with the same architecture).
---

# Obsidian Vault Builder

Build a clean, automated Obsidian vault: flat folder structure with numeric prefixes, one auto-MOC per domain (Dataview), Templater that auto-fills frontmatter on file creation, two-layer tag system, graph-connected via `up:` field.

## When invoked

The user wants you to set up an Obsidian vault in the current working directory (or a specified path). Follow these steps in order.

---

## Step 1 — Detect mode and language

1. Check current working directory for `.obsidian/` folder:
   - **exists** → mode is **rebuild** (existing vault, will be reorganized aggressively)
   - **missing** → mode is **new** (fresh vault will be created)

2. Detect language from the user's recent messages:
   - Cyrillic / Russian phrasing → `ru`
   - Otherwise → `en`

3. Tell the user briefly which mode and language you detected, and warn (only for rebuild) that existing folders will be renamed and old MOC files deleted.

## Step 2 — Gather domain configuration via AskUserQuestion

You need to determine the list of **domains** (top-level content areas) for the vault. Each domain becomes a numbered folder with a single MOC inside.

### For mode=new (empty vault)

Ask the user via AskUserQuestion which domain set they want. Offer:
- **Минимальный универсальный** (RU) / **Minimal universal** (EN) — `Личное`, `Работа`, `Учёба`, `Проекты`, `Ресурсы`
- **Студент-инженер** / **Engineering student** — `Учёба`, `Английский`, `Математика`, `Инженерия`, `AI и технологии`, `Наука`
- **Кастом** / **Custom** — user types comma-separated list of domains

After the user picks, if needed ask a follow-up to collect custom domain names.

### For mode=rebuild (existing vault)

1. List all top-level folders in the vault except: `.obsidian`, `.trash`, `_resources`, `files`, `Templates`, `Daily`, `Inbox`, and any folder starting with a digit (already-prefixed).
2. Show the user the detected domains and ask via AskUserQuestion how to handle them:
   - **Использовать как есть** / **Use as is** — keep names, just add prefixes
   - **Дать переименовать** / **Let me rename** — ask separately for each
   - **Объединить часть** / **Merge some** — user specifies merges in a follow-up

For simplicity, default to "use as is" if user accepts. Auto-assign prefixes starting from 10, in steps of 10 (10, 20, 30, ...).

### Ask about optional plugins

Required plugins (`dataview`, `templater-obsidian`) are always installed.
Ask the user via AskUserQuestion if they want any of these optional ones:
- **Spaced Repetition** (id: `obsidian-spaced-repetition`) — flashcards from notes; very useful for study domains.
- **Obsidian Git** (id: `obsidian-git`) — automatic backup to a git repository.

Multi-select question. User can pick none, one, or both.

### Build the config

Construct a Python dict / JSON object like:

```json
{
  "mode": "new" | "rebuild",
  "lang": "ru" | "en",
  "vault_path": "<absolute path>",
  "domains": [
    { "prefix": "10", "name": "Учёба", "emoji": "🎓", "tag": "study", "old_path": "Учёба" },
    { "prefix": "20", "name": "Английский", "emoji": "🇬🇧", "tag": "english", "old_path": "Английский язык" }
  ],
  "install_plugins": ["dataview", "templater-obsidian", "obsidian-spaced-repetition"]
}
```

`old_path` is only present in rebuild mode (for folders that need to be renamed/moved). Pick reasonable emojis and tags yourself based on domain names. For tag, use a short lowercase Latin slug (`study`, `english`, `engineering`, `ai`, `science`, `personal`, `work`, etc.).

`install_plugins` MUST always include `dataview` and `templater-obsidian`. Add the optional ones the user picked.

## Step 3 — Run the builder

Write the config JSON to a temp file (e.g. `<vault>/_obsidian_skill_config.json`), then invoke:

```bash
python "C:/Users/Name/.claude/skills/obsidian-vault/build_vault.py" --config "<path-to-config.json>"
```

(On non-Windows, use the appropriate skill path under `~/.claude/skills/obsidian-vault/`.)

Watch for errors. Print the script's summary output to the chat.

After success, delete the temp config file.

## Step 4 — Output the post-install guide to chat

Tell the user clearly, in their language:

### What was created
List the top-level folders, explain `00 Система/`, `01 Inbox/`, `02 Daily/`, content domains, `HOME.md`, `README.md`.

### Plugin install status

The script downloads plugins automatically from GitHub releases. Read the script's output:
- If all installs succeeded — tell the user the plugins are ready, they just need to:
  1. Open Obsidian and open the vault folder.
  2. On first launch, Obsidian may show a "Trust author" or "Restricted mode" prompt — click **Turn on community plugins** / **Trust** to allow the pre-installed ones.
  3. Restart Obsidian once if MOCs don't render.
- If any install failed (script printed `✗`), tell the user **only those failed plugins** need manual install:
  1. `Settings` (Ctrl+,) → `Community plugins` → if first time, **Turn on community plugins**.
  2. Click **Browse** → search the plugin name → **Install** → **Enable**.

Do NOT show full manual instructions if everything installed automatically — keep it short.

### Brief usage guide
Explain in the user's language:
- Open `HOME.md` to navigate.
- Create files inside any domain subfolder → frontmatter is filled automatically.
- For unsorted thoughts → put in `01 Inbox/`, sort weekly.
- Cross-cutting topics → use poperechnye tags (see `00 Система/Теги.md` or `00 System/Tags.md`).
- Don't add MOCs to subfolders — Dataview groups them automatically.
- Read `README.md` for the full guide.

---

## Important behavior rules

- **Always work in the current working directory** unless the user gave a different path.
- **Never delete files outside the vault root.**
- **For rebuild mode** — proceed only after the user confirmed they understand existing folders will be renamed. The Python script does NOT create automatic backups; if the user wants safety, suggest they make a copy first or commit to git.
- **Plugins are installed automatically by the build script** — it downloads `manifest.json`, `main.js`, and `styles.css` from each plugin's latest GitHub release and places them in `.obsidian/plugins/<id>/`. Also adds them to `community-plugins.json` so they auto-enable. Do not give manual install instructions unless a download failed.
- **Be concise in chat output** — the README inside the vault has all the deep details.
