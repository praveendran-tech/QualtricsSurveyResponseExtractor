#!/usr/bin/env python3
"""
Qualtrics Survey Export (hardcoded)
Keeps the header row (first non-empty row) and removes the next two rows.
Also strips any trailing metadata lines like {"ImportId":"finished"}.

This handles:
- UTF-8 BOM (utf-8-sig)
- Potential blank first line(s)
- Windows/Unix newlines
"""

import io
import csv
import time
import zipfile
import requests

# ------------------ CONFIGURATION ------------------
QUALTRICS_API_TOKEN = "xxxxxxxx"
DATACENTER = "pdx1"  # e.g., iad1, ca1, eu1
SURVEY_ID = "xxxxxxxxxx"
OUTPUT_FILE = "responses.csv"
# ---------------------------------------------------

BASE_URL = f"https://{DATACENTER}.qualtrics.com/API/v3/surveys/{SURVEY_ID}/export-responses"
HEADERS = {"X-API-TOKEN": QUALTRICS_API_TOKEN, "Content-Type": "application/json"}

def start_export():
    payload = {"format": "csv", "compress": True, "useLabels": True}
    r = requests.post(BASE_URL, headers=HEADERS, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["result"]["progressId"]

def poll_export(progress_id: str) -> str:
    while True:
        r = requests.get(f"{BASE_URL}/{progress_id}", headers=HEADERS, timeout=60)
        r.raise_for_status()
        res = r.json()["result"]
        status = res["status"].lower()
        pct = res.get("percentComplete", 0)
        print(f"    Progress: {pct}% ({status})")
        if status == "complete":
            return res["fileId"]
        if status in {"failed", "error"}:
            raise RuntimeError(f"Export failed: {res}")
        time.sleep(2)

def download_zip(file_id: str) -> bytes:
    r = requests.get(f"{BASE_URL}/{file_id}/file", headers=HEADERS, timeout=300)
    r.raise_for_status()
    return r.content

def extract_first_csv(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for name in z.namelist():
            if name.lower().endswith(".csv"):
                with z.open(name) as f:
                    # Use utf-8-sig to strip BOM if present
                    return f.read().decode("utf-8-sig", errors="replace")
    raise RuntimeError("No CSV found inside export ZIP.")

def clean_drop_rows_2_and_3_keep_header(csv_text: str) -> str:
    """
    Treat the first non-empty row as the header.
    Remove the next two rows (1-based rows 2 and 3 relative to that header).
    Also remove metadata/footer lines like those containing 'ImportId' JSON.
    """
    sio_in = io.StringIO(csv_text)
    reader = csv.reader(sio_in)

    rows = [row for row in reader]

    # Find the header row: first non-empty row
    header_idx = None
    for i, row in enumerate(rows):
        if any(cell.strip() for cell in row):  # non-empty
            header_idx = i
            break

    if header_idx is None:
        # nothing to do
        return csv_text

    # Compute indices to drop: the two rows *after* the header
    drop_indices = {header_idx + 1, header_idx + 2}

    # Filter rows:
    filtered = []
    for i, row in enumerate(rows):
        # Skip the two rows after header
        if i in drop_indices:
            continue

        # Remove typical Qualtrics footer/metadata lines
        joined = " ".join(cell or "" for cell in row).strip()
        if not joined:
            # keep empty lines normally (rare in exports), or skip them; choose to keep
            pass
        if joined.startswith("{") and "ImportId" in joined:
            continue  # footer line like {"ImportId":"finished"}

        filtered.append(row)

    # Write back to CSV text
    sio_out = io.StringIO()
    writer = csv.writer(sio_out, lineterminator="\n")
    writer.writerows(filtered)
    return sio_out.getvalue()

def main():
    print("[+] Starting export job...")
    progress_id = start_export()
    print("[+] Polling export...")
    file_id = poll_export(progress_id)
    print("[+] Downloading results...")
    zip_bytes = download_zip(file_id)
    print("[+] Extracting CSV...")
    csv_text = extract_first_csv(zip_bytes)

    print("[+] Cleaning: keep header, drop rows 2 and 3…")
    cleaned_csv = clean_drop_rows_2_and_3_keep_header(csv_text)

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        f.write(cleaned_csv)

    print(f"[✓] Saved {OUTPUT_FILE} (header kept, rows 2 & 3 removed)")

if __name__ == "__main__":
    main()
