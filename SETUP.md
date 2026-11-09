# Setup and reviewer guide

For the shortest path from clone to first answer, use [QUICKSTART.md](QUICKSTART.md), including its copyable first prompt.

This guide explains how to run the PocketToons reference investigation with the existing coding-agent workflow. The repository is private and requires authorized access. The SQLite database is distributed separately; it is not committed to GitHub.

## What you need

- A local clone of this repository and permission to use it.
- Python 3.9 or newer and SQLite. The data generator uses only Python's standard library; the metric SQL requires SQLite 3.37 or newer. A local build was run with Python 3.9.6 and SQLite 3.51.0. Check your versions with:

  ```sh
  python3 -c "import sqlite3,sys; print('Python:', sys.version); print('SQLite:', sqlite3.sqlite_version)"
  ```
- Your own working Codex or Claude Code environment and available model, with access to the local repository and database. Follow that runtime's account and permission requirements. The selected coding agent performs the reasoning using the framework's shared instructions and tools.
- Enough free local disk space for the database, temporary data and any backup. The reviewed layered database was approximately 680 MiB on the machine where it was prepared; sizes vary.

If you do not already have a local clone, authenticate with GitHub and clone the private repository:

```sh
git clone https://github.com/SoumabrataSarkar/product-analytics-agent.git
cd product-analytics-agent
```

Run the remaining commands from the repository root. Do not place a database, private evidence, secrets or evaluation answer keys in a public repository.

## Option A: download the reviewed database

1. Download the reviewed `pockettoons.sqlite` from the [PocketToons database folder](https://drive.google.com/drive/folders/1owVdIJyOJr7BwMBqT6D8ltph1m5WOPkf?usp=drive_link) (access is granted by the project owner).
2. Download it to a local folder, for example a sibling directory named `pockettoons-data` beside the repository. Let the download finish before opening it. Use a local copy for SQLite access, not a live database on a shared or synchronized drive.
3. Verify the checksum supplied with the download. The reviewed snapshot associated with the initial investigation had SHA-256:

   ```text
   8d39e78bbaa756b594c9e38797490dc1879f2980a05f966aaf62d3919517790b
   ```

   On macOS use `shasum -a 256 /path/to/pockettoons.sqlite`; on Linux use `sha256sum /path/to/pockettoons.sqlite`. Compare against the checksum accompanying the actual download; a later distributed snapshot may legitimately have a different hash.
4. Give the agent the absolute local path and permission to query the file read-only. Do not rerun the generator over this file. Check the actual build and layer availability before using Gold or Silver.

The snapshot above contained 20 source tables, 20 Bronze views, 10 Silver tables and 8 Gold tables. The source data is fictional; the layers are built into the same SQLite file.

## Optional: generate a separate test database

The following example places the database outside the repository, in a new sibling folder. Choose a different output path if a file with this name already exists. The generator refuses to overwrite an existing database.

```sh
mkdir -p ../pockettoons-data
python3 examples/pockettoons/generate.py --output ../pockettoons-data/pockettoons.sqlite
python3 examples/pockettoons/check_data.py ../pockettoons-data/pockettoons.sqlite
python3 examples/pockettoons/build_layers.py ../pockettoons-data/pockettoons.sqlite
```

The first command creates the source tables; the second validates the generated fixture; the third adds Bronze, Silver and Gold to that same file and performs layer reconciliation. Stop if any command reports an error or exits non-zero. The builder modifies the database it is given: apply it to a new file, or use and verify a copy of any database you wish to preserve. Run it on local storage.

A complete fresh run on one Mac with Python 3.9.6 and SQLite 3.51.0 took approximately **24 seconds** to generate the source, **5 minutes 38 seconds** to validate it, and **1 minute 21 seconds** to build and reconcile the layers: roughly **7 minutes 23 seconds**, excluding setup and downloading. Hardware and storage can change the result significantly; allow additional time and disk space. The generator uses a main seed and separate deterministic streams, as described in the [dataset guide](examples/pockettoons/README.md).

The same source code, inputs, seeds and compatible environment are intended to reproduce the source dataset. **Do not assume that a regenerated database is byte-for-byte identical to the downloaded snapshot:** layer build IDs, timestamps and SQLite layout can differ, and manual source edits or code/environment changes can alter contents. In one fresh run using the repository's generator and builder versions for the reviewed snapshot, all 20 logged source-table fingerprints matched the reviewed database; the build IDs were different. This is evidence for that tested version and environment, not a guarantee for future runs. For a defensible comparison, record the generator, builder and registry versions, validate both files and compare source fingerprints in their build logs. Use the downloaded, checksum-verified file when exact snapshot identity matters.

The dataset guide and generation output contain the planted synthetic story and expected values. For an independent evaluation, do not provide them or evaluator answer keys as investigation context to the agent.

## Start an investigation

Use the [first-question prompt in QUICKSTART.md](QUICKSTART.md#3-ask-your-first-question). Replace its database path, output folder and question. This is the same entry point shown in the HTML reference.


Open the repository in your authorized coding-agent runtime and ask it to read [AGENTS.md](AGENTS.md) and the shared [investigation skill](skills/product-analytics-investigation/SKILL.md). Provide your database's absolute path and permission to query it read-only. Ask a business question in plain language; the agent should inspect the appropriate catalog, metric registry and layer contracts, clarify material ambiguity and preserve evidence. It should not require you to write SQL.

For PDF reports, install the optional packages in a virtual environment with `python -m pip install -r requirements.txt` (Python 3.9 gets `reportlab<5`; reportlab 5 needs Python 3.10+). The [tool guide](tools/INVESTIGATION.md) describes the bounded SQL and evidence tools. The [implementation map](docs/architecture/implementation-status.md) distinguishes built components from planned features. Keep query logs and answer keys private; they may contain questions, SQL and returned data. The current tools reduce accidental writes but are not a complete security sandbox.

## Check the installation

Run the test suites from the repository root. Neither needs the downloaded database: each creates small temporary test fixtures. The fixture suite uses the standard library; seven PDF tests in the tools suite require the optional packages.

```sh
python3 -m unittest discover -s tools -p 'test_*.py'              # query, evidence, report and loop tools (29 tests)
python3 -m unittest discover -s examples/pockettoons -p 'test_*.py'  # generator, checks, layers and metric SQL (218 tests)
```

Without the optional packages, the seven PDF tests are skipped. To run all 29 tool tests, first install the packages in a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Dataset overview

The reference fixture describes a fictional streaming product with six months of events, users, sessions, content, payments, subscriptions and marketing. It contains intentional quality issues and uses UTC timestamps. Its [data catalog](docs/examples/pockettoons-data-catalog.md), [metric registry](docs/metrics/metric-registry.md), and [layer contracts](docs/data-layers/pockettoons-layer-contracts.md) define the supported data and analytical rules. It is an example dataset, not a universal schema for other products.
