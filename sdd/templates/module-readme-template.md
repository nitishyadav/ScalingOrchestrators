# ModuleN — <Module Name>

| | |
|---|---|
| Owner | <name> |
| Python package | `<pkg>` |
| Status | Phase 0 / Building / Integrated |
| Contracts owned | C-0x |
| Contracts consumed | C-0y |

## Purpose
<!-- 2–3 sentences. -->

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| MN-F01 <name> | [specs/MN-F01-…/spec.md](specs/) | Draft |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|

## Consumes ← providers
| What | Contract | Provider | Mock I use until integration |
|---|---|---|---|

## Quick start
```bash
make install
make test
make contract-test
make mock   # publish this module's mock for others
make run    # needs env from C-06
```

## Environment variables (from C-06)
| Variable | Default | Purpose |
|---|---|---|

## Layout
```
specs/   src/<pkg>/   tests/{unit,contract,integration}/   mocks/   docs/adr/
```

## Integration notes
<!-- Anything a teammate needs to know when dropping this folder into their tree. -->
