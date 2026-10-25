"""M4 mock (Constitution Art. IV): synthetic, contract-valid C-04/C-05 rows ending now.

Usage:  python mocks/synthetic_rows.py --seconds 600 --anomaly-share 0.2 [--follow 300]
Same as `python -m ids_monitor.synthetic` (kept here so consumers find the mock where the playbook says).
"""
import sys

from ids_monitor.synthetic import main

if __name__ == "__main__":
    sys.exit(main())
