# Entity Helper Versioning

When entity data declares a `$schema` URL, the validation service automatically routes it to the correct entity helper class. Multiple schema versions can be active simultaneously, which is essential during migration periods when upstream systems send a mix of v1 and v2 data.

## The Problem

Validation rules access entity data through logical properties like `loan.principal` and `loan.reference`. But the physical JSON structure changes between schema versions:

| Logical Property | v1.0.0 Physical Path | v2.0.0 Physical Path |
|-----------------|---------------------|---------------------|
| `reference` | `loan_number` | `reference_number` |
| `facility` | `facility_id` | `facility_ref` |
| `rate` | `financial.interest_rate` | `financial.rate` |
| `category` | *(not present)* | `loan_category` |

Without an abstraction layer, every rule would break on every field rename. Entity helpers absorb these changes so rules don't have to.

## How It Works

**1. Entity data declares its schema version:**

```json
{
  "$schema": "https://bank.example.com/schemas/loan/v2.0.0",
  "reference_number": "LN-2024-00002",
  "financial": { "rate": 0.05, ... }
}
```

**2. Business config maps schema URLs to helper classes:**

```yaml
# logic/business-config.yaml

schema_to_helper_mapping:
  "https://bank.example.com/schemas/loan/v1.0.0": "loan_v1.LoanV1"
  "https://bank.example.com/schemas/loan/v2.0.0": "loan_v2.LoanV2"

default_helpers:
  loan: "loan_v1.LoanV1"     # fallback when $schema is absent

version_compatibility:
  allow_minor_version_fallback: true    # v1.1.0 -> v1.0.0 helper
  strict_major_version: true            # unknown major version -> error
```

**3. At runtime, the registry resolves the correct helper:**

```python
from entity_helpers import create_entity_helper

# Factory uses VersionRegistry to pick the right class
helper = create_entity_helper("loan", entity_data)

# Rules use stable logical properties regardless of version
helper.reference   # LoanV1 reads loan_number, LoanV2 reads reference_number
helper.rate        # LoanV1 reads financial.interest_rate, LoanV2 reads financial.rate
```

**4. Rules work unchanged across versions:**

```python
# This rule validates both v1 and v2 loans without modification
if self.entity.principal <= 0:
    return ("FAIL", "Principal must be positive")
```

## Version Resolution Order

When the registry receives entity data, it resolves the helper class in this order:

1. **Exact match** — `$schema` URL matches an entry in `schema_to_helper_mapping`
2. **Minor version fallback** — `v1.2.0` falls back to `v1.0.0` mapping (if `allow_minor_version_fallback: true`)
3. **Default helper** — entity type matches an entry in `default_helpers` (when `$schema` is absent)
4. **Error** — `ValueError` if nothing matches (strict major version check rejects unknown majors)

## File Layout

```
logic/
├── models/
│   ├── loan.schema.v1.0.0.json       # v1 JSON Schema
│   └── loan.schema.v2.0.0.json       # v2 JSON Schema (breaking changes)
│
├── entity_helpers/
│   ├── __init__.py                    # create_entity_helper() factory
│   ├── version_registry.py           # VersionRegistry + get_registry() singleton
│   ├── loan_v1.py                    # LoanV1 — maps logical props to v1 fields
│   └── loan_v2.py                    # LoanV2 — maps logical props to v2 fields
│
└── business-config.yaml              # schema_to_helper_mapping lives here
```

Helper classes are per **major** version. Minor versions (`v1.0.0`, `v1.1.0`) share the same helper since minor changes are backward-compatible additions.

## Adding a New Schema Version

1. Create the schema file: `logic/models/loan.schema.v3.0.0.json` (set `$id` and `version`)
2. Create the helper: `logic/entity_helpers/loan_v3.py` with field mappings for the new schema
3. Add the mapping to `logic/business-config.yaml`:
   ```yaml
   schema_to_helper_mapping:
     "https://bank.example.com/schemas/loan/v3.0.0": "loan_v3.LoanV3"
   ```

No rule changes needed. No code changes outside `logic/`. The registry picks up the new mapping on the next process start.

## Immutability

Helper files are **immutable versioned artifacts**. `loan_v1.py` is never edited once published — it maps logical properties to v1.0.0 physical fields, and that mapping is frozen. When the schema evolves to v3, a new `loan_v3.py` is created. The business config is the only file that changes (to add the new mapping entry). See the immutability model in [TECHNICAL-DESIGN.md](TECHNICAL-DESIGN.md) Section 3 for details.

## Schema File Naming

Schema files follow the convention `{entity_type}.schema.v{version}.json`. Each schema declares a canonical `$id` URL:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://bank.example.com/schemas/loan/v1.0.0",
  "title": "Loan Schema v1.0.0",
  "version": "1.0.0"
}
```

When entity data references a schema via a `file://` or `https://` URI ending in `.json`, the version registry fetches the schema and extracts the canonical `$id` for matching. This means the same mapping works regardless of whether the schema is served locally or from a remote URL.

## Field Access Tracking

Entity helpers optionally record which properties each rule accesses during execution:

```python
helper = create_entity_helper("loan", entity_data, track_access=True)
# ... rule executes, accessing helper.principal and helper.balance ...
dependencies = helper.get_accesses()
# [("principal", "financial.principal_amount"), ("balance", "financial.outstanding_balance")]
```

This powers the `discover-rules` API endpoint for impact analysis and documentation generation.
