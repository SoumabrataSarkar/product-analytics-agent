"""Read and assemble canonical metric SQL from the shared Metric Registry.

Each SQL block in docs/metrics/metric-registry.md starts with `-- metric: <name>`.
An optional next line `-- requires: a, b=c` names the blocks the query reads:
`a` is available to the query as a CTE named `a`; `b=c` makes block `c`
available under the name `b`. Tests and the fixture checker run the assembled
registry text directly, so the registry remains the single source of each
definition.
"""
from pathlib import Path
import re

REGISTRY = Path(__file__).resolve().parents[2] / 'docs' / 'metrics' / 'metric-registry.md'
BLOCK = re.compile(r'```sql\n-- metric: ([a-z0-9_]+)\n(.*?)```', re.S)
REQUIRES = re.compile(r'-- requires: (.*)\n')


def _blocks(registry=REGISTRY):
    blocks = {}
    for name, body in BLOCK.findall(Path(registry).read_text()):
        if name in blocks:
            raise KeyError(f'registry SQL block {name!r} is defined more than once')
        requires = []
        found = REQUIRES.match(body)
        if found:
            body = body[found.end():]
            for item in found.group(1).split(','):
                alias, _, target = item.strip().partition('=')
                requires.append((alias, target or alias))
        blocks[name] = (requires, body.strip())
    return blocks


def load_sql(name, registry=REGISTRY):
    """Return the runnable query for block `name`, with its required blocks as CTEs."""
    blocks = _blocks(registry)

    def build(block, stack=()):
        if block not in blocks:
            raise KeyError(f'no registry SQL block named {block!r}')
        if block in stack:
            raise ValueError(f'circular registry dependency: {" -> ".join(stack + (block,))}')
        requires, body = blocks[block]
        if not requires:
            return body
        ctes = ',\n'.join(f'{alias} AS (\n{build(target, stack + (block,))}\n)' for alias, target in requires)
        for prefix in ('WITH RECURSIVE ', 'WITH '):
            if body.upper().startswith(prefix):
                return f'{prefix}{ctes},\n{body[len(prefix):]}'
        return f'WITH {ctes}\n{body}'

    return build(name)


def with_monthly(sql, name='mau_monthly'):
    """Prefix a query that reads `mau_monthly` with the registered monthly SQL as a CTE."""
    return f'WITH mau_monthly AS ({load_sql(name)})\n{sql}'
