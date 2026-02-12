# Entity Helper Versioning

Entity helpers are versioned by schema. When entity data declares a `$schema` URL, the runner automatically loads the correct helper class. Multiple schema versions can be active simultaneously — useful during migration periods when some data is still on v1 while new data arrives as v2.

## How it works

Each piece of entity data includes a `$schema` field:

```json
{
  "$schema": "https://bank.example.com/schemas/loan/v2.0.0",
  "id": "LOAN-20001",
  "reference_number": "LN-2024-00002",
  ...
}
```

`config.yaml` maps schema URLs to helper classes:

```yaml
schema_to_helper_mapping:
  "https://bank.example.com/schemas/loan/v1.0.0": "loan_v1.LoanV1"
  "https://bank.example.com/schemas/loan/v2.0.0": "loan_v2.LoanV2"

default_helpers:
  loan: "loan_v1.LoanV1"   # used when $schema is absent

version_compatibility:
  allow_minor_version_fallback: true   # v1.1.0 falls back to v1.0.0 helper
  strict_major_version: true           # unknown major version raises an error
```

At runtime, `VersionRegistry` reads these mappings and `create_entity_helper()` returns the right class. Rules always work through the stable logical interface (`loan.reference`, `loan.rate`, etc.) regardless of which helper version is underneath.

## File layout

```
models/
├── loan.schema.v1.0.0.json    # v1 schema
└── loan.schema.v2.0.0.json    # v2 schema (breaking changes)

python-runner/entity_helpers/
├── loan_v1.py                 # LoanV1 for v1.x.x data
├── loan_v2.py                 # LoanV2 for v2.x.x data (renamed fields)
└── version_registry.py        # VersionRegistry + get_registry() singleton
```

Helper classes are per major version. Minor versions (`v1.0.0`, `v1.1.0`) share the same helper since minor changes are backward-compatible additions.

## Adding a new schema version

1. Create `models/loan.schema.v3.0.0.json` with `"$id"` and `"version"` updated.
2. Create `entity_helpers/loan_v3.py` with field mappings for the new schema.
3. Add the mapping to `config.yaml`:
   ```yaml
   "https://bank.example.com/schemas/loan/v3.0.0": "loan_v3.LoanV3"
   ```

No other code changes needed. The registry picks up the new mapping on the next process start.

## Version resolution order

1. Exact `$schema` URL match in `schema_to_helper_mapping`
2. Minor version fallback: `v1.2.0` → finds `v1.0.0` mapping (if `allow_minor_version_fallback: true`)
3. `default_helpers` by entity type (when `$schema` is absent)
4. `ValueError` if nothing matches

## Schema file naming

Schema files follow: `{entity_type}.schema.v{version}.json`

`rule_001_v1` (JSON schema validation) extracts the version from `$schema` and loads the corresponding file automatically.

## Versioned helper classes

Each major schema version has its own dedicated helper class (`LoanV1`, `LoanV2`, etc.). All code uses explicit version references - there is no unversioned `Loan` class. This makes version dependencies clear and prevents accidental mixing of incompatible versions.
