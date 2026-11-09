# Investigation loop: early foundation

The loop connects a caller-supplied model adapter to the bounded read-only
SQLite tool and an evidence log. It is an early implementation, not a
validated analytical agent. A real provider adapter, independent evaluation,
chart generation and report rendering are not included.

Run tests from the repository root:

```sh
python3 -m unittest discover -s tools -p 'test_*.py'
```

## Adapter interface

The CLI invokes a local command without a shell. The command must read one JSON
object from standard input and write one JSON action object to standard output
on each invocation. It receives the question, dataset-specific catalog and
registry, current query budget and the history of earlier results. It can
return a `query`, `clarify` or `finish` action as described in the
`system` field of the request.

```sh
python3 tools/investigation.py --database /path/to/fixture.sqlite \
  --question 'Your business question' --snapshot-id 'verified-by-caller' \
  --catalog docs/examples/pockettoons-data-catalog.md \
  --registry docs/metrics/metric-registry.md \
  --log /private/path/new-evidence.jsonl \
  --adapter /path/to/your-model-adapter
```

The supplied snapshot ID and source-layer labels are caller/model assertions,
not verified hashes or proof of correct routing. The system prompt is
guidance, not an enforcement mechanism for analytical correctness: inspect SQL,
definitions, evidence and conclusions. The loop caps query attempts at nine,
limits the model's stated hypothesis rounds, and applies the query tool's
read-only, row and per-query time limits. It stops on a model error or an
evidence/database error and does not invent a successful answer.

The log includes SQL, question, parameters and query results for traceability.
The adapter receives the same potentially sensitive data and may send it to an
external model depending on its implementation. Use only an approved runtime,
avoid confidential data, choose a private log location, and do not commit
logs, database files, keys or assignment material. A new log file is required.

The evidence log alone is not a finished report. A completed response is
model-generated and still needs independent factual and numerical validation.
