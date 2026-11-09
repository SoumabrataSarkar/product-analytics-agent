# PocketToons Product Analytics Agent: quick start

The agent runs inside your own Codex or Claude Code environment. The repository contains its instructions, metric definitions, catalog, and query tools; it is not a standalone chat application. The SQLite database is downloaded separately.

## 1. What you need

- Access to the private GitHub repository and to the [PocketToons database folder](https://drive.google.com/drive/folders/1owVdIJyOJr7BwMBqT6D8ltph1m5WOPkf?usp=drive_link).
- Git, Python 3.9 or newer, and SQLite 3.37 or newer through Python. Check with:

  ```sh
  python3 -c "import sys, sqlite3; print('Python:', sys.version); print('SQLite:', sqlite3.sqlite_version)"
  ```

- A working Codex or Claude Code environment, including any account, model access, and permissions required by that runtime. Open the cloned repository in it.
- Enough free space for the approximately 680 MiB database and your investigation outputs. The database is synthetic.

## 2. Clone and download

Clone the repository, using your authorized GitHub account:

```sh
git clone https://github.com/SoumabrataSarkar/product-analytics-agent.git
cd product-analytics-agent
```

Download **`pockettoons.sqlite`** from the Drive folder to a local folder outside the repository, for example `~/pockettoons-data/pockettoons.sqlite`. Let the download complete before querying it. Use a local copy, not a live database in a synchronized folder. The one file already contains Bronze, Silver and Gold; do not run the generator or layer builder on it.

Verify the download matches the reviewed file:

```sh
# macOS
shasum -a 256 ~/pockettoons-data/pockettoons.sqlite
# Linux
sha256sum ~/pockettoons-data/pockettoons.sqlite
```

Expected SHA-256:

```text
8d39e78bbaa756b594c9e38797490dc1879f2980a05f966aaf62d3919517790b
```

If the hash differs, stop and ask the project owner whether the shared snapshot changed; do not overwrite or regenerate it. Substitute the real path above if you saved it elsewhere.

## 3. Ask your first question

Open the cloned repository in Codex or Claude Code. Paste the following prompt, replacing the database path and output folder. The example question is ready to use; change it to your own when you are ready. Use a full absolute path, for example `/Users/yourname/pockettoons-data/pockettoons.sqlite` on macOS or `/home/yourname/pockettoons-data/pockettoons.sqlite` on Linux.

```text
Use this repository to investigate a PocketToons product question.

Database: /absolute/path/to/pockettoons.sqlite
I authorize you to read and query this file. Do not modify, regenerate, or overwrite it. If you cannot access it, ask me instead of choosing another database.

Read AGENTS.md and follow the shared product analytics investigation skill. Read the architecture, data catalog, metric registry, and layer contracts. Check the database build status and available Bronze, Silver, and Gold objects; record the snapshot and versions. Use the repository's read-only query and evidence tools for material checks. Ask me if missing information could change the answer; do not invent definitions.

Work independently: do not read docs/evaluations/, evaluation-results/, submission/, previous investigation reports, answer keys, the generator's answer-bearing README, or question-specific investigation guides.

Question: How did monthly active users change from April through September 2026 across all identified users? Use the approved MAU definition and explain any coverage limits.

Output folder: /absolute/path/to/a/new/investigation-folder
Save a Markdown report and the evidence logs there. Record the start and end times, query count, and repository commit or download date. If the folder already exists, use a new folder rather than overwriting an earlier run.
```

The agent may ask follow-up questions if the periods, population, or metric definition are ambiguous. It should supply evidence and explain limitations; results should be reviewed by a human. No SQL is required from the person asking the question.

## 4. Reports and further detail

If you request a PDF report, the repository's report generator needs the Python packages in [`requirements.txt`](requirements.txt). In a Python virtual environment, install them with `python -m pip install -r requirements.txt` (on Python 3.9 this selects `reportlab<5`, because reportlab 5 needs Python 3.10 or newer). The agent can then follow the repository's report workflow. Text answers and read-only query tooling use the Python standard library.

See [SETUP.md](SETUP.md) for full setup, regeneration instructions, and limitations. Keep the database and investigation evidence out of Git and do not share private query logs unintentionally. The scenario evaluation and its remaining limitations are described in [the evaluation results](docs/evaluations/results.md) and [the evaluation PDF](submission/eval-results.pdf); do not read it during an independent investigation.
