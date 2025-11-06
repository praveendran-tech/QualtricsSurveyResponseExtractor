#!/usr/bin/env python3
"""
Qualtrics → Box (merge multiple surveys into ONE CSV) — requests-only

- For each Survey ID:
    1) Export responses (CSV in ZIP)
    2) Clean: keep header, drop rows 2 & 3, remove {"ImportId":"finished"}
- Merge all surveys into a single CSV:
    * Superset header across all surveys
    * Align rows to that superset (missing cols -> "")
- Upload one file to Box:
    * Overwrite if same name exists; else create new
    * If overwrite forbidden (403), upload timestamped copy

Requirements:
    pip install requests
"""

import io
import csv
import time
import zipfile
import datetime
import requests
from typing import Optional, Tuple, List, Dict

# ======================== CONFIG ========================

# Qualtrics
QUALTRICS_API_TOKEN = "xxxxxxxxxxxxxxxxxxxxxxx"
DATACENTER = "pdx1"  # e.g., iad1, ca1, eu1
SURVEY_IDS = "xxxx,xxxxx,xxx,xxx"  # comma-separated

# Output (single combined file)
CSV_FILENAME = "xxx.xlsx"

# Box
BOX_DEVELOPER_TOKEN = "xxxxxx"  # short-lived (~60 min)
BOX_FOLDER_ID = "xxx"  # "0" root or your folder ID like "347751241234"

# ==================== END CONFIG ========================


# ---------- Qualtrics helpers ----------
def q_base_url(survey_id: str) -> str:
    return f"https://{DATACENTER}.qualtrics.com/API/v3/surveys/{survey_id}/export-responses"

def q_headers() -> dict:
    return {"X-API-TOKEN": QUALTRICS_API_TOKEN, "Content-Type": "application/json"}

def q_start_export(survey_id: str) -> Tuple[str, str]:
    base = q_base_url(survey_id)
    payload = {"format": "csv", "compress": True, "useLabels": True}
    r = requests.post(base, headers=q_headers(), json=payload, timeout=60)
    _raise_for_status(r, f"Qualtrics start export ({survey_id})")
    progress_id = r.json()["result"]["progressId"]
    return progress_id, base

def q_poll_export(progress_id: str, base_url: str) -> str:
    waited = 0.0
    interval = 2.0
    while True:
        r = requests.get(f"{base_url}/{progress_id}", headers=q_headers(), timeout=60)
        _raise_for_status(r, "Qualtrics poll export")
        res = r.json()["result"]
        status = (res.get("status") or "").lower()
        pct = res.get("percentComplete", 0)
        print(f"    Export progress: {pct}% ({status})")
        if status == "complete":
            return res["fileId"]
        if status in {"failed", "error"}:
            raise RuntimeError(f"Qualtrics export failed: {res}")
        time.sleep(interval)
        waited += interval
        if waited > 600:
            raise TimeoutError("Qualtrics export polling exceeded 10 minutes.")

def q_download_zip(base_url: str, file_id: str) -> bytes:
    r = requests.get(f"{base_url}/{file_id}/file", headers=q_headers(), timeout=300)
    _raise_for_status(r, "Qualtrics download zip")
    return r.content

def extract_first_csv_text(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for name in z.namelist():
            if name.lower().endswith(".csv"):
                with z.open(name) as f:
                    return f.read().decode("utf-8-sig", errors="replace")
    raise RuntimeError("No CSV found inside Qualtrics export ZIP.")


# ---------- Cleaning & Parsing ----------
def clean_keep_header_drop_2_3(csv_text: str) -> List[List[str]]:
    """
    Return cleaned CSV as list-of-rows:
      - Keep first *non-empty* row as header
      - Drop next two rows
      - Remove footer lines like {"ImportId":"finished"}
      - Skip empty rows
    """
    rows = list(csv.reader(io.StringIO(csv_text)))
    header_idx = next((i for i, row in enumerate(rows) if any((c or "").strip() for c in row)), None)
    if header_idx is None:
        return []

    drop = {header_idx + 1, header_idx + 2}

    cleaned: List[List[str]] = []
    for i, row in enumerate(rows):
        if i in drop:
            continue
        joined = " ".join((c or "") for c in row).strip()
        if not joined or (joined.startswith("{") and "ImportId" in joined):
            continue
        cleaned.append(row)

    return cleaned  # includes header as first row


def rows_to_header_and_dicts(rows: List[List[str]]) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Convert parsed rows to (header, list_of_row_dicts).
    Empty header cells become unique column names like 'col_1' if needed.
    """
    if not rows:
        return [], []

    header = rows[0]
    # Normalize duplicate/blank headers
    normalized = []
    seen = {}
    for idx, name in enumerate(header):
        base = (name or "").strip() or f"col_{idx+1}"
        candidate = base
        k = 1
        while candidate in seen:
            k += 1
            candidate = f"{base}_{k}"
        seen[candidate] = True
        normalized.append(candidate)
    header = normalized

    dict_rows: List[Dict[str, str]] = []
    for r in rows[1:]:
        d = {}
        for i, col in enumerate(header):
            d[col] = r[i] if i < len(r) else ""
        dict_rows.append(d)
    return header, dict_rows


# ---------- Merge helpers ----------
def merge_tables(tables: List[Tuple[List[str], List[Dict[str, str]]]]) -> List[List[str]]:
    """
    Merge multiple (header, rows_as_dict) tables into one CSV rows list.
    Superset header preserves order of first appearance; new columns appended.
    """
    sup_header: List[str] = []
    seen = set()
    for hdr, _ in tables:
        for col in hdr:
            if col not in seen:
                seen.add(col)
                sup_header.append(col)

    merged_rows: List[List[str]] = [sup_header]
    for hdr, dict_rows in tables:
        # Map each row dict to sup_header order
        for d in dict_rows:
            merged_rows.append([d.get(col, "") for col in sup_header])
    return merged_rows


def rows_to_csv_bytes(rows: List[List[str]]) -> bytes:
    sio = io.StringIO()
    writer = csv.writer(sio, lineterminator="\n")
    writer.writerows(rows)
    return sio.getvalue().encode("utf-8")


# ---------- Box helpers ----------
BOX_API_BASE = "https://api.box.com/2.0"
BOX_UPLOAD_BASE = "https://upload.box.com/api/2.0"

def box_auth_header() -> dict:
    return {"Authorization": f"Bearer {BOX_DEVELOPER_TOKEN}"}

def box_list_folder_items(folder_id: str, limit: int = 1000) -> list:
    url = f"{BOX_API_BASE}/folders/{folder_id}/items"
    params = {"limit": limit, "offset": 0}
    r = requests.get(url, headers=box_auth_header(), params=params, timeout=60)
    _raise_for_status(r, "Box list folder items")
    return r.json().get("entries", [])

def box_find_file_in_folder_by_name(folder_id: str, filename: str) -> Optional[str]:
    for item in box_list_folder_items(folder_id):
        if item.get("type") == "file" and item.get("name") == filename:
            return item.get("id")
    return None

def box_upload_new_file(csv_bytes: bytes, filename: str, folder_id: str):
    url = f"{BOX_UPLOAD_BASE}/files/content"
    files = {
        "attributes": (None, f'{{"name":"{filename}","parent":{{"id":"{folder_id}"}}}}', "application/json"),
        "file": (filename, io.BytesIO(csv_bytes), "text/csv"),
    }
    r = requests.post(url, headers=box_auth_header(), files=files, timeout=300)
    _raise_for_status(r, "Box upload new file")
    entry = r.json()["entries"][0]
    print(f"[✓] Uploaded new Box file '{entry['name']}' (id={entry['id']}).")

def safe_overwrite_or_new(csv_bytes: bytes, filename: str, folder_id: str):
    file_id = box_find_file_in_folder_by_name(folder_id, filename)
    if not file_id:
        box_upload_new_file(csv_bytes, filename, folder_id)
        return
    r = requests.post(
        f"{BOX_UPLOAD_BASE}/files/{file_id}/content",
        headers=box_auth_header(),
        files={"file": (filename, io.BytesIO(csv_bytes), "text/csv")},
        timeout=300,
    )
    if r.status_code == 201:
        print(f"[✓] Overwrote Box file '{filename}' with new version.")
        return
    if r.status_code == 403:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        alt = f"{filename.rsplit('.',1)[0]}_{ts}.csv"
        print(f"[warn] 403 overwrite denied → uploading as new file '{alt}'")
        box_upload_new_file(csv_bytes, alt, folder_id)
        return
    _raise_for_status(r, "Box upload new version")


# ---------- Error helper ----------
def _raise_for_status(resp: requests.Response, context: str):
    if resp.ok:
        return
    try:
        j = resp.json()
    except Exception:
        j = None
    msg = f"{context}: HTTP {resp.status_code}"
    msg += f" | body={str(j)[:600]}" if j else f" | body={resp.text[:600]}"
    raise requests.HTTPError(msg)


# ---------- Main ----------
def main():
    survey_list = [s.strip() for s in SURVEY_IDS.split(",") if s.strip()]
    if not survey_list:
        raise SystemExit("No Survey IDs provided in SURVEY_IDS.")

    tables: List[Tuple[List[str], List[Dict[str, str]]]] = []

    for sid in survey_list:
        print("\n===========================================")
        print(f"[+] Processing survey: {sid}")
        try:
            pid, base_url = q_start_export(sid)
            fid = q_poll_export(pid, base_url)
            print("[+] Downloading export ZIP…")
            zip_bytes = q_download_zip(base_url, fid)

            print("[+] Cleaning & parsing CSV…")
            csv_text = extract_first_csv_text(zip_bytes)
            cleaned_rows = clean_keep_header_drop_2_3(csv_text)
            if not cleaned_rows:
                print(f"[warn] {sid}: empty/invalid export; skipping.")
                continue

            hdr, dict_rows = rows_to_header_and_dicts(cleaned_rows)
            if not hdr:
                print(f"[warn] {sid}: no header detected; skipping.")
                continue

            tables.append((hdr, dict_rows))
        except Exception as e:
            print(f"[error] {sid}: {e}")

    if not tables:
        raise SystemExit("No data collected from any survey; nothing to upload.")

    print("[+] Merging all surveys into one CSV…")
    merged_rows = merge_tables(tables)
    csv_bytes = rows_to_csv_bytes(merged_rows)

    print(f"[+] Uploading combined file to Box as '{CSV_FILENAME}'…")
    safe_overwrite_or_new(csv_bytes, CSV_FILENAME, BOX_FOLDER_ID)

    print("\n[✓] All done.")


if __name__ == "__main__":
    main()
