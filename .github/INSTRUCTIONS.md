# STOKS — Development & GitHub Instructions

## Virtual Environment

This project uses a Python virtual environment in the `env/` directory.

### Activation (REQUIRED before any work)

**Windows (PowerShell):**
```powershell
& env\Scripts\Activate.ps1
```

**Unix / macOS:**
```bash
source env/bin/activate
```

### Installing Dependencies

After activating the environment:
```bash
pip install -r requirements.txt
```

> **Rule:** Never install packages directly via `pip install <pkg>`. Always add the dependency to `requirements.txt` first, then run `pip install -r requirements.txt`.

---

## Running the Scanner

```bash
python -m src.main
```

Or with options:
```bash
python -m src.main --sector-mode simple --config config.yaml
```

---

## GitHub Pages

- The repository is configured to serve GitHub Pages from the **root of the `main` branch**.
- `index.html` at the repo root is the entry point.
- The Python pipeline generates `index.html` and all files under `site/`.
- After a pipeline run, commit and push the updated site files to publish.

### Deployment Steps
1. Activate environment and run the scanner pipeline
2. Review generated `index.html` and `site/` directory
3. `git add index.html site/`
4. `git commit -m "Update scan results YYYY-MM-DD"`
5. `git push origin main`

---

## Project Structure

```
STOKS/
├── index.html              ← Generated (GitHub Pages root)
├── site/                   ← Generated site assets
├── src/                    ← Python source code
├── config.yaml             ← User configuration
├── requirements.txt        ← Python dependencies
├── docs/                   ← Specs and documentation
├── tests/                  ← Unit + golden tests
├── runs/                   ← Timestamped run outputs
├── exports/                ← CSV exports
├── .github/                ← GitHub instructions
├── .copilot/               ← Copilot skills
├── .gitignore
└── env/                    ← Virtual environment (git-ignored)
```

---

## Branching & Commits

- `main` branch is the source of truth and the GitHub Pages source.
- Use descriptive commit messages.
- Generated files (`index.html`, `site/`) are committed to `main` so GitHub Pages can serve them.

---

## Notes for AI Assistants (Copilot / Claude)

- **Always activate the virtual environment** before running any Python command.
- **Never install packages directly** — update `requirements.txt` and let the user install.
- The `env/` directory is git-ignored and should never be committed.
- The `runs/` directory contains ephemeral run artifacts and is git-ignored.
- See `docs/SPEC_v1.0.md` for the full system specification.
