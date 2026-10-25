"""M1-T060 — synthetic CIC TrafficLabelling CSVs with the real files' quirks (C-01 §3.2):
padded header names, a duplicated `Fwd Header Length` column, latin-1 encoding with the 0x96 dash, empty rows.
"""
import csv
import hashlib
from pathlib import Path

from ids_contracts import events as ev

HEADER = ["Flow ID", " Source IP", " Source Port", " Destination IP", " Destination Port", " Protocol", " Timestamp",
          " Fwd Header Length", "Total Length of Fwd Packets", " SYN Flag Count", " ACK Flag Count",
          " Fwd Header Length", " Label"]

DEFAULT_LABELS = {
    "Monday-WorkingHours": ["BENIGN", "BENIGN", "BENIGN"],
    "Tuesday-WorkingHours": ["BENIGN", "FTP-Patator", "SSH-Patator"],
    "Wednesday-workingHours": ["DoS Hulk", "BENIGN", "Heartbleed"],
    "Thursday-WorkingHours-Morning-WebAttacks": ["Web Attack \x96 XSS", "BENIGN", "BENIGN"],
    "Thursday-WorkingHours-Afternoon-Infilteration": ["Infiltration", "BENIGN", "BENIGN"],
    "Friday-WorkingHours-Morning": ["Bot", "BENIGN", "BENIGN"],
    "Friday-WorkingHours-Afternoon-PortScan": ["PortScan", "PortScan", "BENIGN"],
    "Friday-WorkingHours-Afternoon-DDos": ["DDoS", "BENIGN", "DDoS"],
}


def row(src="192.168.10.5", dst="192.168.10.50", port="80", nbytes="100", syn="0", ack="1",
        label="BENIGN", ts="3/7/2017 9:00"):
    return ["flow", src, "5555", dst, port, "6", ts, "20", nbytes, syn, ack, "20", label]


def write_csv(path: Path, rows) -> None:
    with open(path, "w", encoding="latin-1", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(rows)


def default_rows(stem: str):
    return [row(src=f"172.16.0.{i + 1}", port=str(80 + i), nbytes=str(100 * (i + 1)), syn=str(i % 2), label=lab)
            for i, lab in enumerate(DEFAULT_LABELS[stem])]


def make_raw(data_dir: Path, rows_by_stem=None) -> dict:
    """Write all 8 source files under data_dir/raw/TrafficLabelling; return a CIC_REFERENCE-shaped dict for them."""
    raw = Path(data_dir) / "raw" / "TrafficLabelling"
    raw.mkdir(parents=True, exist_ok=True)
    reference = {}
    for day in ev.REPLAY_DAYS:
        for stem in ev.CIC_FILE_ORDER[day]:
            rows = (rows_by_stem or {}).get(stem, default_rows(stem))
            path = raw / f"{stem}{ev.CIC_FILE_SUFFIX}"
            write_csv(path, rows)
            reference[stem] = (hashlib.sha256(path.read_bytes()).hexdigest(), None)
    return reference
