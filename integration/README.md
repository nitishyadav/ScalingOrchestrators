# Integration

This folder holds what is needed to connect the four modules. It is jointly owned.
**Integration lead (proposed): M1 owner**, because M1 owns the platform. Confirm in P0.

## Planned integrations

| ID | Seam | Modules | Contracts | Phase | Proves |
|---|---|---|---|---|---|
| I-01 | Kafka events | M1 → M3 | C-01, C-06 | P2 | Events reach Spark at the target rate with no schema errors |
| I-02 | Detection bundle and features | M2 → M3 | C-02, C-03 | P2 | Spark features equal the golden fixture, and the bundle loads and scores in the Spark image |
| I-03 | Anomaly store and metrics | M3 → M4 | C-04, C-05 | P2 | Rows and metrics written by Spark render in the dashboard |
| I-04 | Full pipeline | M1→M3→M4 + M2 | All | P3 | E2E smoke test, then E1/E2/E3 runnable from the M4 harness |

Use [../sdd/templates/integration-checklist-template.md](../sdd/templates/integration-checklist-template.md)
and save results as `checklists/I-0x-<slug>.md`.

## Swapping in a teammate's module

1. Replace the folder `ModuleN_<name>/` in your tree with the owner's copy. Do not merge the two.
2. Confirm that `contracts/` is identical on both sides (same versions).
3. Run `make contract-test` in **all four** module folders.
4. If they all pass, run the relevant integration checklist. If any fail, the failing side has a contract
   violation: fix it, or raise a CR if the contract itself is wrong.

## Planned contents (built in P2/P3)

```
integration/
├── checklists/            ← signed I-xx checklists
├── docker-compose.yml     ← overlay that runs each module's `run` on M1's platform
├── .env.example           ← generated from C-06
└── e2e/                   ← end-to-end smoke tests using the golden fixtures
```
