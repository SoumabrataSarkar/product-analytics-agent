"""Read canonical metric SQL from the shared Metric Registry.

Each SQL block in docs/metrics/metric-registry.md starts with a line
`-- metric: <name>`. Tests and the fixture checker run these blocks directly,
so the registry remains the single source of the definition.
"""
from pathlib import Path
import re

REGISTRY = Path(__file__).resolve().parents[2] / 'docs' / 'metrics' / 'metric-registry.md'
BLOCK = re.compile(r'```sql\n-- metric: ([a-z0-9_]+)\n(.*?)```', re.S)


def load_sql(name, registry=REGISTRY):
    """Return the SQL block registered under `name`; fail if it is missing or repeated."""
    found = [sql.strip() for key, sql in BLOCK.findall(Path(registry).read_text()) if key == name]
    if len(found) != 1:
        raise KeyError(f'expected one registry SQL block named {name!r}, found {len(found)}')
    return found[0]


def with_monthly(sql, name='mau_monthly'):
    """Prefix a query that reads `mau_monthly` with the registered monthly SQL as a CTE."""
    return f'WITH mau_monthly AS ({load_sql(name)})\n{sql}'
