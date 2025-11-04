# 🧾 Qualtrics Survey Response Export Script

## 📘 Overview
This Python script connects to the **Qualtrics API** and downloads all responses from a specific survey.  
It automatically cleans the data by:
- **Keeping the header row (column names)**
- **Removing rows 2 and 3** (which usually contain metadata or redundant labels)
- **Saving the cleaned data** into a local CSV file.

---

## ⚙️ Configuration

Before running the script, open the `.py` file and **update these values** near the top:

| Variable | Description | Example |
|-----------|--------------|----------|
| `QUALTRICS_API_TOKEN` | Your **Qualtrics personal API token** from *Account Settings → Qualtrics IDs → API* | `"QxG9AbCdEf123..."` |
| `DATACENTER` | The **data center (brand ID)** of your Qualtrics account (visible in your Qualtrics URL) | `"pdx1"`, `"iad1"`, `"ca1"`, etc. |
| `SURVEY_ID` | The **Survey ID** for the survey you want to export (found under *Survey → Survey ID*) | `"SV_abc123XYZ456"` |
| `OUTPUT_FILE` | The name of the **output CSV file** | `"responses.csv"` |

---

## 💻 How to Run

Open a terminal in the folder containing the script and run:

```bash
py .\QualtricsSurveyResponseExtractor.py
