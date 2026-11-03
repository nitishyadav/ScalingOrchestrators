# M2-F03 ML diagnosis (2026-11-03)

Same model as `ids_model.train` (seed 42, inputs bytes_per_flow, port_ratio, syn_ack_ratio, syn_share). Test split used for diagnosis only.

## Verdict per test category

| Category | Windows | AUC vs benign | ML recall at p99.9 | Reading |
|---|---|---|---|---|
| DDoS | 9 | 0.991 | 0.000 | THRESHOLD problem: attacks rank high but fall under the threshold |
| PortScan | 8 | 0.991 | 0.000 | THRESHOLD problem: attacks rank high but fall under the threshold |

## Test: attack score position (17 attack of 21,279 windows)

Percentile of the benign-train score distribution at which attack windows land (5 / 50 / 95 % of attack windows).

| Category | AUC | Benign-train percentile (q05 / median / q95) | Recall at p90 | p99 | p99.9 |
|---|---|---|---|---|---|
| DDoS | 0.991 | 99.6 / 99.6 / 99.6 | 1.000 | 1.000 | 0.000 |
| PortScan | 0.991 | 99.6 / 99.6 / 99.7 | 1.000 | 1.000 | 0.000 |

ML-only test precision / recall / FPR by threshold percentile:

| Percentile | Precision | Recall | FPR |
|---|---|---|---|
| p90 | 0.008 | 1.000 | 10.319% |
| p95 | 0.012 | 1.000 | 6.486% |
| p97 | 0.016 | 1.000 | 5.075% |
| p98 | 0.022 | 1.000 | 3.589% |
| p99 | 0.027 | 1.000 | 2.855% |
| p99.5 | 0.058 | 1.000 | 1.289% |
| p99.9 | 0.000 | 0.000 | 0.024% |

## Validation: attack score position (37 attack of 119,536 windows)

Percentile of the benign-train score distribution at which attack windows land (5 / 50 / 95 % of attack windows).

| Category | AUC | Benign-train percentile (q05 / median / q95) | Recall at p90 | p99 | p99.9 |
|---|---|---|---|---|---|
| DoS GoldenEye | 0.995 | 99.2 / 99.6 / 99.6 | 1.000 | 1.000 | 0.000 |
| DoS Hulk | 0.997 | 99.6 / 99.7 / 99.8 | 1.000 | 1.000 | 0.000 |
| DoS slowloris | 1.000 | 100.0 / 100.0 / 100.0 | 1.000 | 1.000 | 1.000 |
| FTP-Patator | 0.997 | 99.7 / 99.7 / 99.8 | 1.000 | 1.000 | 0.000 |
| Infiltration | 0.998 | 99.7 / 99.7 / 99.9 | 1.000 | 1.000 | 0.167 |
| SSH-Patator | 0.997 | 99.7 / 99.7 / 99.8 | 1.000 | 1.000 | 0.000 |
| Web Attack - Brute Force | 0.997 | 99.8 / 99.8 / 99.8 | 1.000 | 1.000 | 0.000 |
| Web Attack - XSS | 0.997 | 99.7 / 99.7 / 99.7 | 1.000 | 1.000 | 0.000 |

ML-only validation precision / recall / FPR by threshold percentile:

| Percentile | Precision | Recall | FPR |
|---|---|---|---|
| p90 | 0.004 | 1.000 | 7.790% |
| p95 | 0.007 | 1.000 | 4.137% |
| p97 | 0.011 | 1.000 | 2.894% |
| p98 | 0.015 | 1.000 | 2.013% |
| p99 | 0.023 | 1.000 | 1.296% |
| p99.5 | 0.050 | 0.973 | 0.572% |
| p99.9 | 0.022 | 0.054 | 0.076% |

## Mean shift of each model input, test attack windows vs benign-train (after log1p + scaling, in train SD)

| Category | bytes_per_flow | port_ratio | syn_ack_ratio | syn_share |
|---|---|---|---|---|
| DDoS | +1.74 | -7.55 | -0.46 | -0.56 |
| PortScan | -0.88 | -9.75 | -0.71 | -0.70 |
