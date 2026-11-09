# Setup and reviewer guide

This guide explains how to run the PocketToons reference investigation with the existing coding-agent workflow. The repository is private and requires authorized access. The SQLite database is distributed separately; it is not committed to GitHub.

## What you need

- A local clone of this repository and permission to use it.
- Python 3 and SQLite. The data generator uses only Python's standard library; the metric SQL requires SQLite 3.37 or newer. A local build was run with Python 3.9.6 and SQLite 3.51.0. Check your versions with:

  ```sh
  python3 -c "import sqlite3,sys; print('Python:', sys.version); print('SQLite:', sqlite3.sqlite_version)"
  ```
- A working Codex or Claude Code environment with access to your local workspace and database. Follow that runtime's account and permission requirements. The repository does not bundle a model or guarantee a particular runtime.
- Enough free local disk space for the database, temporary data and any backup. The reviewed layered database was approximately 680 MiB on the machine where it was prepared; sizes vary.

If you do not already have a local clone, authenticate with GitHub and clone the private repository:\n\n```sh\ngit clone https://github.com/SoumabrataSarkar/product-analytics-agent.git\ncd product-analytics-agent\n```\n\nRun the remaining commands from the repository root. Do not place a database, private evidence, secrets or evaluation answer keys in a public repository.

## Option A: download the reviewed database

1. Obtain the authorized download link for the reviewed `pockettoons.sqlite` from the submission or project owner. A download link and access settings must be supplied separately.
2. Download it to a local folder, for example a sibling directory named `pockettoons-data` beside the repository. Let the download finish before opening it. Use a local copy for SQLite access, not a live database on a shared or synchronized drive.
3. Verify the checksum supplied with the download. The reviewed snapshot associated with the initial investigation had SHA-256:

   ```text
   8d39e78bbaa756b594c9e38797490dc1879f2980a05f966aaf62d3919517790b
   ```

   On macOS use `shasum -a 256 /path/to/pockettoons.sqlite`; on Linux use `sha256sum /path/to/pockettoons.sqlite`. Compare against the checksum accompanying the actual download; a later distributed snapshot may legitimately have a different hash.
4. Give the agent the absolute local path and permission to query the file read-only. Do not rerun the generator over this file. Check the actual build and layer availability before using Gold or Silver.

The snapshot above contained 20 source tables, 20 Bronze views, 10 Silver tables and 8 Gold tables. The source data is fictional; the layers are built into the same SQLite file.

## Option B: generate a fresh database

The following example places the database outside the repository, in a new sibling folder. Choose a different output path if a file with this name already exists. The generator refuses to overwrite an existing database.

```sh
mkdir -p ../pockettoons-data
python3 examples/pockettoons/generate.py --output ../pockettoons-data/pockettoons.sqlite
python3 examples/pockettoons/check_data.py ../pockettoons-data/pockettoons.sqlite
python3 examples/pockettoons/build_layers.py ../pockettoons-data/pockettoons.sqlite
```

The first command creates the source tables; the second validates the generated fixture; the third adds Bronze, Silver and Gold to that same file and performs layer reconciliation. Stop if any command reports an error or exits non-zero. The builder modifies the database it is given: apply it to a new file, or use and verify a copy of any database you wish to preserve. Run it on local storage.

On one Mac, source generation took about **24 seconds** and the source validation took about **5 minutes 38 seconds**. A previous layer build recorded approximately **73 seconds**. These are separate observations, not a complete end-to-end benchmark: together they suggest roughly **7–8 minutes**, plus setup time, but hardware and storage can change the result significantly. Allow additional time and disk space. The generator uses a main seed and separate deterministic streams, as described in the [dataset guide](examples/pockettoons/README.md).

The same source code, inputs, seeds and compatible environment are intended to reproduce the source dataset. **Do not assume that a regenerated database is byte-for-byte identical to the downloaded snapshot:** layer build IDs, timestamps and SQLite layout can differ, and manual source edits or code/environment changes can alter contents. For a defensible comparison, record the generator, builder and registry versions, validate both files and compare source fingerprints in their build logs. Use the downloaded, checksum-verified file when exact snapshot identity matters.

The dataset guide and generation output contain the planted synthetic story and expected values. For an independent evaluation, do not provide them or evaluator answer keys as investigation context to the agent.

## Start an investigation

Open the repository in your authorized coding-agent runtime and ask it to read [AGENTS.md](AGENTS.md) and the shared [investigation skill](skills/product-analytics-investigation/SKILL.md). Provide your database's absolute path and permission to query it read-only. Ask a business question in plain language; the agent should inspect the appropriate catalog, metric registry and layer contracts, clarify material ambiguity and preserve evidence. It should not require you to write SQL.

The [tool guide](tools/INVESTIGATION.md) describes the bounded SQL and evidence tools. The [implementation map](docs/architecture/implementation-status.md) distinguishes built components from planned features. Keep query logs and answer keys private; they may contain questions, SQL and returned data. The current tools reduce accidental writes but are not a complete security sandbox.

## Dataset overview

The reference fixture describes a fictional streaming product with six months of events, users, sessions, content, payments, subscriptions and marketing. It contains intentional quality issues and uses UTC timestamps. Its [data catalog](docs/examples/pockettoons-data-catalog.md), [metric registry](docs/metrics/metric-registry.md), and [layer contracts](docs/data-layers/pockettoons-layer-contracts.md) define the supported data and analytical rules. It is an example dataset, not a universal schema for other products.
