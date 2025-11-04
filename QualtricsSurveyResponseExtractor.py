#!/usr/bin/env python3
"""
Qualtrics → Box (overwrite if exists) — no Box SDK required

- Exports survey responses via Qualtrics API
- Keeps header (first non-empty row), removes rows 2 & 3
- Strips footer lines like {"ImportId":"finished"}
- Uploads to a Box folder:
    * if file exists (same name), uploads a **new version** (overwrite)
    * otherwise, creates a new file

Requirements:
    pip install requests
"""

import io
import csv
import time
import zipfile
import requests
from typing import Optional, Tuple

# ------------------ QUALTRICS CONFIG ------------------
QUALTRICS_API_TOKEN = "xxxxxxxx"
DATACENTER = "xxxx"               # e.g., iad1, ca1, eu1
SURVEY_ID = "xxxxxx"      # e.g., SV_abc123
CSV_FILENAME = "xxxxx"    # the name that will appear in Box
# ------------------------------------------------------

# ------------------ BOX CONFIG ------------------------
BOX_DEVELOPER_TOKEN = "xxxxxx"   # short-lived (~60 mins)
BOX_FOLDER_ID = "xxxxxx"                                 # "0" = root; or e.g., "1234567890"
# ------------------------------------------------------

# Qualtrics endpoints
Q_BASE = f"https://{DATACENTER}.qualtrics.com/API/v3/surveys/{SURVEY_ID}/export-responses"
Q_HEADERS = {"X-API-TOKEN": QUALTRICS_API_TOKEN, "Content-Type": "application/json"}

# Box endpoints / headers
BOX_API_BASE = "https://api.box.com/2.0"
BOX_UPLOAD_BASE = "https://upload.box.com/api/2.0"
BOX_AUTH_HEADER = {"Authorization": f"Bearer {BOX_DEVELOPER_TOKEN}"}


# ------------------ Qualtrics helpers ------------------
def q_start_export() -> str:
    payload = {"format": "csv", "compress": True, "useLabels": True}
    r = requests.post(Q_BASE, headers=Q_HEADERS, json=payload, timeout=60)
    _raise_for_status(r, "Qualtrics start export")
    return r.json()["result"]["progressId"]

def q_poll_export(progress_id: str) -> str:
    while True:
        r = requests.get(f"{Q_BASE}/{progress_id}", headers=Q_HEADERS, timeout=60)
        _raise_for_status(r, "Qualtrics poll export")
        res = r.json()["result"]
        status = res["status"].lower()
        pct = res.get("percentComplete", 0)
        print(f"    Qualtrics export: {pct}% ({status})")
        if status == "complete":
            return res["fileId"]
        if status in {"failed", "error"}:
            raise RuntimeError(f"Qualtrics export failed: {res}")
        time.sleep(2)

def q_download_zip(file_id: str) -> bytes:
    r = requests.get(f"{Q_BASE}/{file_id}/file", headers=Q_HEADERS, timeout=300)
    _raise_for_status(r, "Qualtrics download zip")
    return r.content

def extract_first_csv_text(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for name in z.namelist():
            if name.lower().endswith(".csv"):
                with z.open(name) as f:
                    return f.read().decode("utf-8-sig", errors="replace")  # strip BOM if present
    raise RuntimeError("No CSV found inside export ZIP.")


# ------------------ Cleaning ------------------
def clean_keep_header_drop_2_3(csv_text: str) -> bytes:
    """
    Returns cleaned CSV bytes:
      - keep first *non-empty* row as header
      - drop the next two rows after that (rows 2 & 3)
      - remove typical Qualtrics footer JSON lines like {"ImportId":"finished"}
    """
    rows = list(csv.reader(io.StringIO(csv_text)))

    # Find header row (first non-empty)
    header_idx = None
    for i, row in enumerate(rows):
        if any((c or "").strip() for c in row):
            header_idx = i
            break
    if header_idx is None:
        # nothing usable; return original
        return csv_text.encode("utf-8")

    drop = {header_idx + 1, header_idx + 2}

    filtered = []
    for i, row in enumerate(rows):
        if i in drop:
            continue
        joined = " ".join((c or "") for c in row).strip()
        if not joined:
            continue
        if joined.startswith("{") and "ImportId" in joined:
            continue
        filtered.append(row)

    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(filtered)
    return out.getvalue().encode("utf-8")


# ------------------ Box helpers (requests only) ------------------
def box_list_folder_items(folder_id: str, limit: int = 1000) -> list:
    """List first `limit` items in a folder (simple pagination could be added if needed)."""
    url = f"{BOX_API_BASE}/folders/{folder_id}/items"
    params = {"limit": limit, "offset": 0}
    r = requests.get(url, headers=BOX_AUTH_HEADER, params=params, timeout=60)
    _raise_for_status(r, "Box list folder items")
    return r.json().get("entries", [])

def box_find_file_in_folder_by_name(folder_id: str, filename: str) -> Optional[str]:
    """Return file_id if a file with this name exists in the folder, else None."""
    items = box_list_folder_items(folder_id)
    for item in items:
        if item.get("type") == "file" and item.get("name") == filename:
            return item.get("id")
    return None

def box_upload_new_file(csv_bytes: bytes, filename: str, folder_id: str) -> Tuple[str, str]:
    """
    Upload a new file. Returns (file_id, file_name).
    """
    url = f"{BOX_UPLOAD_BASE}/files/content"
    headers = {"Authorization": BOX_AUTH_HEADER["Authorization"]}
    files = {
        "attributes": (None, f'{{"name":"{filename}","parent":{{"id":"{folder_id}"}}}}', "application/json"),
        "file": (filename, io.BytesIO(csv_bytes), "text/csv"),
    }
    r = requests.post(url, headers=headers, files=files, timeout=300)
    _raise_for_status(r, "Box upload new file")
    entry = r.json()["entries"][0]
    return entry["id"], entry["name"]

def box_upload_new_version(file_id: str, csv_bytes: bytes, filename: str) -> Tuple[str, str]:
    """
    Upload a new version to an existing file (overwrite).
    Returns (file_id, file_name).
    """
    url = f"{BOX_UPLOAD_BASE}/files/{file_id}/content"
    headers = {"Authorization": BOX_AUTH_HEADER["Authorization"]}
    files = {
        "file": (filename, io.BytesIO(csv_bytes), "text/csv"),
    }
    r = requests.post(url, headers=headers, files=files, timeout=300)
    _raise_for_status(r, "Box upload new version")
    entry = r.json()["entries"][0]
    return entry["id"], entry["name"]


# ------------------ Error helper ------------------
def _raise_for_status(resp: requests.Response, context: str) -> None:
    if resp.ok:
        return
    try:
        j = resp.json()
    except Exception:
        j = None
    msg = f"{context}: HTTP {resp.status_code}"
    if j:
        msg += f" | body={str(j)[:600]}"
    else:
        msg += f" | body={resp.text[:600]}"
    raise requests.HTTPError(msg)


# ------------------ Main ------------------
def main():
    print("[+] Starting Qualtrics export…")
    pid = q_start_export()
    fid = q_poll_export(pid)
    print("[+] Downloading export ZIP…")
    zip_bytes = q_download_zip(fid)
    print("[+] Cleaning CSV…")
    csv_text = extract_first_csv_text(zip_bytes)
    cleaned = clean_keep_header_drop_2_3(csv_text)

    print("[+] Checking Box for existing file…")
    existing_file_id = box_find_file_in_folder_by_name(BOX_FOLDER_ID, CSV_FILENAME)

    if existing_file_id:
        print(f"[+] Found existing file '{CSV_FILENAME}' (id={existing_file_id}). Uploading new version…")
        file_id, name = box_upload_new_version(existing_file_id, cleaned, CSV_FILENAME)
        print(f"[✓] Overwrote Box file '{name}' (id={file_id}) with a new version.")
    else:
        print(f"[+] No existing file named '{CSV_FILENAME}'. Uploading as new…")
        file_id, name = box_upload_new_file(cleaned, CSV_FILENAME, BOX_FOLDER_ID)
        print(f"[✓] Uploaded new Box file '{name}' (id={file_id}).")

if __name__ == "__main__":
    main()
