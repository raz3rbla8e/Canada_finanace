# 🍁 CanadaFinance

A free, private, self-hosted personal finance dashboard for Canadians. Runs locally on your laptop — your bank data never leaves your computer.

![Dashboard preview](https://via.placeholder.com/800x400/0e0f11/6ee7b7?text=CanadaFinance+Dashboard)

## Features

- **Import bank CSVs** — drag and drop, auto-detects your bank
- **Auto-categorization** — 300+ merchant rules built in, gets smarter as you use it
- **Monthly dashboard** — income, expenses, net saved, savings rate
- **Month-over-month comparison** — see if you're spending more than last month
- **Budget targets** — set limits per category with visual progress bars
- **Recurring transaction detection** — automatically spots subscriptions and habits
- **Year in review** — full annual breakdown with top categories
- **Open search** — search "costco" and get both Costco Gas and Wholesale
- **Edit & learn** — fix a category once, it remembers forever
- **Manual entries** — add cash, e-transfers, or any transaction not in a CSV
- **Export CSV** — export any month or all time for sharing
- **Dark/light mode**
- **Zero cost** — no subscriptions, no cloud, no ads

---

## Supported Banks

| Bank | Account Type | CSV Available | Notes |
|------|-------------|---------------|-------|
| **Tangerine** | Chequing | ✅ | E-transfers in from named people → Income |
| **Tangerine** | Credit Card | ✅ | All expenses imported |
| **Wealthsimple** | Chequing | ✅ | Direct deposit paychecks only |
| **RBC** | Chequing | ✅ | Download from online banking |
| **TD** | Chequing | ✅ | EasyWeb → Download Transactions → CSV |
| **CIBC** | Chequing | ✅ | Account Activity → Export |
| **Scotiabank** | Chequing | ✅ | Online banking → Download |
| **BMO** | Chequing | ✅ | Online banking → Export |
| **National Bank** | Chequing | ✅ | Bilingual (EN/FR) supported |

> **Credit cards at most banks** (TD, RBC, CIBC, BMO) are only available as PDFs — not CSVs. Tangerine is the main exception. If your bank only gives you PDFs, try a free converter like [DocuClipper](https://docuclipper.com) to get a CSV first.

---

## Setup

**Requirements:** Python 3.8+, pip

```bash
# 1. Clone or download this repo
git clone https://github.com/yourusername/canadafinance
cd canadafinance

# 2. Install dependency (just Flask)
pip install -r requirements.txt

# 3. Run
python app.py

# 4. Open in browser
# http://localhost:5000
```

That's it. A `finance.db` file is created automatically on first run.

---

## Usage

### Importing transactions

1. Log into your bank's online banking
2. Download your transactions as CSV (usually under "Account Activity" → "Export" or "Download")
3. Open **http://localhost:5000** → **Import CSV** tab
4. Drag and drop one or more CSV files
5. Done — duplicates are automatically skipped

**You can import the same file multiple times safely.** The app uses a hash of date + name + amount + account to deduplicate — it will never double-count.

### Monthly routine (around the 17th)

```
1. Download CSVs from each bank
2. Drag into Import CSV tab
3. Check dashboard for the new month
4. Fix any UNCATEGORIZED transactions by clicking them
```

### Fixing categories

Click any transaction row → Edit modal → Change category → Save.

The merchant name is saved to your `learned_merchants` database. Next time that merchant appears in a CSV, it's auto-categorized correctly. You can manage or delete learned merchants in **Settings**.

### Manual transactions

Click **Add Transaction** in the sidebar for:
- Cash purchases
- E-transfers to your dad (car payment, etc.)
- Any expense not captured by a bank CSV

### Setting budgets

Go to **Settings** → Monthly Budgets → pick a category and set your limit. Progress bars appear on the dashboard showing how close you are.

### Carpool income (e-transfers)

Go to **Settings** → Carpool People → add the first names of people who pay you (e.g. "jonas", "vaibhav"). When Tangerine Chequing CSVs are imported, incoming e-transfers from those names are auto-tagged as **Income / Carpool**.

---

## Data & Privacy

- All data is stored in `finance.db` — a local SQLite file on your machine
- Nothing is sent to any server, ever
- To back up your data: copy `finance.db` somewhere safe
- To start fresh: delete `finance.db` and restart the app

---

## File Structure

```
canadafinance/
  app.py          ← Everything (Flask app + all logic + frontend)
  finance.db      ← Your data (created on first run, gitignored)
  requirements.txt
  README.md
```

---

## Adding a new bank

If your bank isn't supported, open `app.py` and look for the `detect_bank()` and `parse_*` functions. Add a new detection rule based on the CSV header row, then write a parser following the same pattern as the existing ones. PRs welcome.

---

## Contributing

Issues and PRs welcome. Please don't commit any real transaction data.

---

## License

MIT
