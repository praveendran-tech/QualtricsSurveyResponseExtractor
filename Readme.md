```markdown
# 🧾 Qualtrics Survey Response Export Script

## 📘 What this does
This Python script connects to the **Qualtrics API** and downloads all responses from a specific survey.  
It then cleans the data by:
- **Keeping the header row (column names)**
- **Removing rows 2 and 3** (commonly metadata/redundant labels)
- Saving the result (or sending it to your chosen destination, depending on your script version)

---

## ⬇️ Download & Place the File

1) **Download the script file** (e.g., `QualtricsSurveyResponseExtractor.py`) from where it was shared with you.  
2) **Move the file to your Desktop**:
   - Windows: drag the file into `Desktop` in File Explorer.
   - macOS: drag it into the Desktop area in Finder.

---

## 🖥️ Open Terminal from VS Code
1) Open **Visual Studio Code**.  
2) Click **File → Open Folder…** and open your **Desktop** folder.  
3) In the VS Code window, open the **Terminal**:
   - Click the **Terminal** menu → **New Terminal**, **OR**
   - Click the **terminal icon** (to the right of the “Launchpad”-style text/toolbar in the top area of VS Code) to open the integrated terminal at your Desktop folder.

You should now see a terminal prompt like:
```

PS C:\Users<you>\Desktop>

```
or on macOS:
```

~/Desktop %

````

---

## 🛠️ Update Your Script (Survey ID & API Token)

Open `QualtricsSurveyResponseExtractor.py` in VS Code and find the **CONFIGURATION** section at the top. Update these values:

| Variable | Description | What to put |
|---|---|---|
| `QUALTRICS_API_TOKEN` | Your Qualtrics **Personal Access Token** | A long string like `QxG9AbCdEf...` |
| `DATACENTER` | Your Qualtrics **data center/brand ID** | e.g., `pdx1`, `iad1`, `ca1` (check your Qualtrics URL or Account Settings) |
| `SURVEY_ID` | Your **Survey ID** | Looks like `SV_abc123XYZ456` |

> You **do not** need to change any other code.

---

## 🔑 How to Get a Qualtrics API Token (Layman’s terms)

1) **Log in** to Qualtrics in your browser.  
2) Click your user **profile icon** (top-right) → **Account Settings**.  
3) Go to the **Qualtrics IDs** tab (sometimes under “API”).  
4) Find **API** or **Personal Access Token**.  
   - If you see a **Generate Token** button, click it.  
   - Copy the token shown (a long string of letters/numbers).  
5) **Paste** that token into your script as the value for `QUALTRICS_API_TOKEN`.  
6) Also note your **Datacenter** on this page (e.g., `pdx1`, `iad1`) and put it into `DATACENTER`.  
7) To find your **Survey ID**, open your survey → click **Survey ID** in the same Qualtrics IDs section or from the survey’s settings; it will look like `SV_...`.

> Treat your token like a password. Don’t share it publicly.

---

## ▶️ Run the Script

In the VS Code terminal (opened to Desktop), run:

**Windows (PowerShell):**
```powershell
py .\QualtricsSurveyResponseExtractor.py
````

**macOS / Linux:**

```bash
python3 QualtricsSurveyResponseExtractor.py
```

You should see progress messages like:

```
[+] Starting export job…
    Progress: 60% (inProgress)
    Progress: 100% (complete)
[✓] Saved responses.csv (rows 2 & 3 removed, header kept)
```

---

## 🧩 If Python/Pip Isn’t Set Up

* Check Python:
  **Windows:**

  ```powershell
  python --version
  ```

  If not found, install from [https://www.python.org/downloads/](https://www.python.org/downloads/) and **check “Add Python to PATH”** during install.

* If the script needs extra packages:

  ```powershell
  py -m ensurepip --upgrade
  py -m pip install requests
  ```

  (Most versions of this script only need `requests`, which we install above.)

---

## 🆘 Quick Troubleshooting

* **401/403 from Qualtrics** → Token is wrong/expired, wrong `DATACENTER`, or your account lacks survey access.
* **“Survey not found”** → Double-check `SURVEY_ID` (must start with `SV_`).
* **CSV looks odd** → That’s normal when Qualtrics includes label rows. This script **keeps the first header row** and **removes rows 2 & 3** for a clean dataset.

---

**Author:** Pranav Raveendran
**Last Updated:** November 2025

```
::contentReference[oaicite:0]{index=0}
```
