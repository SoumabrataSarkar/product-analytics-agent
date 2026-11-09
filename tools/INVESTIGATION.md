# Investigation tools

The intended runtime is **Codex or Claude Code**. A user opens the project and
asks a question; the coding agent follows the shared investigation instructions,
consults the relevant data catalog and metric registry, uses the read-only
query and evidence tools, and produces an evidence-backed answer.

The shared investigation skill is in
[`skills/product-analytics-investigation/SKILL.md`](../skills/product-analytics-investigation/SKILL.md).
Its instructions and query command have targeted tests, but they have not yet
been independently evaluated in a full investigation. The repository does
not yet provide a verified turnkey investigation experience.

## Existing tools

- `safe_query.py` runs one bounded, read-only SQLite query. Its default
  timeout is 30 seconds per query; results may be truncated at the row limit.
- `evidence_log.py` records query context and outcomes to a new local file,
  separate from the database. The caller supplies the snapshot identifier;
  it is not automatically verified.
- `evidence_query.py` invokes both tools for a single query from JSON on
  standard input and creates a new local evidence log for that query.
- `investigation.py` is an experimental, model-neutral Python loop exercised
  with scripted callbacks in tests. It is not the Codex or Claude Code skill,
  and it does not provide a ready-to-use model connection.

Run the tests from the repository root:

```sh
python3 -m unittest discover -s tools -p 'test_*.py'
```

## Safety and evidence

SQL, questions, parameters, results and evidence files can contain sensitive
information. Use only authorized datasets; store evidence privately and do not
commit data, logs, keys or confidential assignment material. The read-only
tool reduces accidental database changes but is not a complete security sandbox.

Source-layer labels and snapshot identifiers are assertions supplied by the
caller, not proof that routing or freshness is correct. Independently check
metric definitions, joins, data quality, SQL, numerical results and claims.
The skill requires end-to-end evaluation. Report output, visualizations and
the independent evaluation suite remain work to complete.
