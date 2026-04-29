# 🍁 CanadaFinance

A free, private, self-hosted personal finance dashboard for Canadians. Runs locally on your laptop — your bank data never leaves your computer.

## Features

- **Import bank CSVs** — drag and drop, auto-detects your bank format
- **Unknown CSV wizard** — if your bank isn't recognized, a step-by-step wizard maps columns and saves the config for future imports
- **Auto-categorization** — 300+ merchant rules built in, gets smarter as you use it
- **Monthly dashboard** — income, expenses, net saved, savings rate
- **Month-over-month comparison** — see if you're spending more or less than last month
- **Budget targets** — set spending limits per category with visual progress bars
- **Monthly averages** — see your average spend per category over the last 6 months
- **Recurring/subscription detection** — automatically identifies merchants that charge you every month, flags price changes
- **Year in review** — full annual breakdown with monthly bars and top 5 categories
- **Account filter** — filter transactions by bank account (TD, Tangerine, etc.)
- **Open search** — search "costco" and get both Costco Gas and Wholesale across all months
- **Bulk actions** — select multiple transactions and delete, categorize, or hide them all at once
- **Edit & learn** — fix a category once, it remembers forever (learned merchants)
- **Retro-fix** — when you fix a category, the app automatically re-categorizes similar UNCATEGORIZED transactions
- **Manual entries** — add cash, e-transfers, or any transaction not in a CSV
- **Import rules** — create rules to auto-hide, label, or force-show transactions at import time
- **Rule templates** — one-click presets (Default, Freelancer, Student, Self-Employed, Carpool)
- **Hide/unhide transactions** — hide internal transfers or noise; view and restore hidden items
- **Custom categories** — add, rename, or delete categories with emoji icons
- **Export CSV** — export any month or all time (re-importable — full round trip)
- **Backup/restore** — download your entire database as a backup, restore from a backup file
- **Dark/light mode** — toggle in the sidebar
- **Zero cost** — no subscriptions, no cloud, no ads, no tracking

---

## Supported Banks

| Bank | Account Type | CSV Available | Notes |
|------|-------------|---------------|-------|
| **Tangerine** | Chequing | ✅ | E-transfers, memo field included |
| **Tangerine** | Credit Card | ✅ | All purchases and refunds |
| **Wealthsimple** | Chequing | ✅ | Auto-detects account type from CSV |
| **RBC** | Chequing | ✅ | Debit/Credit columns |
| **TD** | Chequing | ✅ | EasyWeb → Download Transactions → CSV |
| **CIBC** | Chequing | ✅ | Account Activity → Export |
| **Scotiabank** | Chequing | ✅ | Single amount column |
| **BMO** | Chequing | ✅ | Withdrawals/Deposits columns |
| **National Bank** | Chequing | ✅ | Bilingual (EN/FR) supported |
| **Any other bank** | Any | ✅ | Use the CSV wizard to map columns — config is saved automatically |

> **Credit cards at most banks** (TD, RBC, CIBC, BMO) are only available as PDFs — not CSVs. Tangerine is the main exception. If your bank only gives you PDFs, try a free converter like [DocuClipper](https://docuclipper.com) to get a CSV first.

---

## Setup

### Easiest: double-click to launch

1. Install [Python 3.9+](https://www.python.org/downloads/) (check "Add Python to PATH" during install)
2. Download this repo (green **Code** button → **Download ZIP**), unzip it
3. **Windows:** double-click `start.bat`
4. **Mac/Linux:** open a terminal in the folder, run `chmod +x start.sh && ./start.sh`

The app installs dependencies automatically on first launch and opens your browser.

### Manual setup

```bash
git clone https://github.com/raz3rbla8e/Canada-finance
cd Canada-finance
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

### Standalone `.exe` (no Python needed)

Download `CanadaFinance.exe` from the [Releases](https://github.com/raz3rbla8e/Canada-finance/releases) page — just run it.

To build the `.exe` yourself:
```bash
pip install pyinstaller
pyinstaller canada_finance.spec
# Output: dist/CanadaFinance.exe
```

### Docker

```bash
docker build -t canada-finance .
docker run -p 5000:5000 -v finance_data:/app canada-finance
```

### Running tests

```bash
pip install -e ".[dev]"
pytest
```

**156 tests** across 8 test files covering all endpoints, bank detection, security, and edge cases.

**Environment variables** (optional — see `.env.example`):
- `SECRET_KEY` — custom session secret (auto-generated if not set)
- `DB_PATH` — custom database file path (defaults to `finance.db`)

---

## Usage

### Importing transactions

1. Log into your bank's online banking
2. Download your transactions as CSV (usually under "Account Activity" → "Export" or "Download")
3. Open **http://localhost:5000** → **Import CSV** tab
4. Drag and drop one or more CSV files
5. Done — duplicates are automatically skipped

**You can import the same file multiple times safely.** The app uses a SHA-256 hash of date + name + amount + account to deduplicate — it will never double-count.

**Unknown banks?** If the CSV format isn't recognized, a wizard opens automatically. You map the date, description, and amount columns, name the bank, preview the parsed data, and save. A YAML config is created in `banks/` and future imports auto-detect.

**Re-importing your own exports?** If you export a CSV from CanadaFinance and re-import it (or share it with a friend), the app recognizes its own format and preserves all categories, types, and account names.

### Monthly routine

```
1. Download CSVs from each bank
2. Drag into Import CSV tab
3. Check dashboard for the new month
4. Fix any UNCATEGORIZED transactions by clicking them
```

### Fixing categories

Click any transaction row → Edit modal → Change category → Save.

The merchant name is saved to your `learned_merchants` database. Next time that merchant appears in a CSV, it's auto-categorized correctly. The app also retro-fixes any other UNCATEGORIZED transactions that match.

You can manage or delete learned merchants in **Settings → Learned Merchants**.

### Bulk actions

In the **Transactions** tab, use the checkboxes to select multiple transactions, then:
- **Categorize** — assign the same category to all selected
- **Hide** — hide selected transactions from your dashboard
- **Delete** — remove selected transactions permanently

### Manual transactions

Click **Add Transaction** in the sidebar for:
- Cash purchases
- E-transfers (e.g. car payment to family)
- Any expense not captured by a bank CSV

### Setting budgets

Go to **Settings → Monthly Budgets** → pick a category and set your limit. Progress bars appear on the dashboard showing how close you are (green → amber → red).

### Recurring & subscriptions

The dashboard automatically detects merchants that charge you in 3 or more distinct months (Netflix, Spotify, gym membership, etc.) and shows:
- Average monthly amount
- Total monthly committed spend
- Price change warnings (e.g. Netflix went from $16.49 to $17.99)

### Import rules

Go to **Settings → Import Rules** to create rules that run automatically on every CSV import:

- **Hide** — suppress internal transfers, credit card payments, etc. from your dashboard
- **Label** — auto-tag matching transactions with a specific type/category (e.g. label all Interac e-transfers from a specific person as Income / Freelance)
- **Pass** — force-show transactions that would otherwise be hidden by another rule

Rules have conditions (description contains, amount greater than, etc.) and first match wins by priority. You can test rules against your existing data before saving.

**Templates:** One-click presets for common setups — Default, Freelancer, Student, Self-Employed, Carpool/Commuter. Load a template and customize.

### Hidden transactions

Transactions hidden by rules (or manually) don't affect your dashboard numbers. View them from the **Transactions** tab → **Hidden** toggle. You can unhide any transaction to restore it.

### Custom categories

In **Settings → Categories**, you can:
- Add new expense or income categories with emoji icons
- Rename existing categories (all transactions are updated automatically)
- Delete categories (with option to reassign transactions to another category)

### Year in review

Switch to the **Year Review** tab to see:
- Total income, expenses, and net saved for the year
- Monthly bar chart comparing income vs. expenses
- Top 5 spending categories for the year

### Backup & restore

- **Backup:** Settings → Download Backup (downloads your `finance.db` file with a timestamp)
- **Restore:** Settings → Restore from Backup (upload a `.db` file to overwrite your current data)
- **Export CSV:** Export tab → download all transactions as CSV (can be re-imported)

---

## Data & Privacy

- All data is stored in `finance.db` — a local SQLite file on your machine
- Nothing is sent to any server, ever
- The only external request is loading Google Fonts and Chart.js from CDNs (for the UI)
- Session tokens use SHA-256 and are auto-generated per install
- CSRF protection on all mutating API endpoints
- To back up your data: use the in-app backup, or copy `finance.db` somewhere safe
- To start fresh: delete `finance.db` and restart the app

---

## File Structure

```
Canada-finance/
├── app.py                          ← Entry point
├── pyproject.toml                  ← Package config and dependencies
├── requirements.txt                ← Pip dependencies
├── start.bat                       ← Windows launcher (auto-installs deps)
├── start.sh                        ← Mac/Linux launcher
├── canada_finance.spec             ← PyInstaller build config
├── Dockerfile                      ← Docker container config
├── .env.example                    ← Environment variable reference
├── banks/                          ← YAML bank configs (auto-detect CSV formats)
│   ├── bmo_chequing.yaml
│   ├── canada_finance_export.yaml  ← Recognizes re-imported exports
│   ├── cibc_chequing.yaml
│   ├── national_bank.yaml
│   ├── rbc_chequing.yaml
│   ├── scotiabank.yaml
│   ├── tangerine_credit.yaml
│   ├── tangerine_debit.yaml
│   ├── td_chequing.yaml
│   └── wealthsimple.yaml
├── rules/templates/                ← Import rule presets
│   ├── default.yaml
│   ├── freelancer.yaml
│   ├── student.yaml
│   ├── self_employed.yaml
│   └── carpool_commuter.yaml
├── canada_finance/                 ← Application package
│   ├── __init__.py                 ← Flask app factory, CSRF middleware
│   ├── __main__.py                 ← python -m canada_finance
│   ├── config.py                   ← Paths and config constants
│   ├── models/
│   │   └── database.py             ← SQLite schema, init, tx_hash, migrations
│   ├── routes/
│   │   ├── __init__.py             ← Blueprint registration
│   │   ├── main.py                 ← Homepage, health check
│   │   ├── transactions.py         ← CRUD, search, pagination, bulk actions, account filter
│   │   ├── import_export.py        ← CSV import/export, bank wizard, backup/restore
│   │   ├── summary.py              ← Dashboard, year review, averages, recurring detection
│   │   ├── settings.py             ← Budgets, categories, learned merchants
│   │   └── rules.py                ← Import rules CRUD, templates, test/apply
│   ├── services/
│   │   ├── categorization.py       ← 300+ keyword → category mapping
│   │   ├── csv_parser.py           ← YAML-driven CSV parsing engine
│   │   ├── helpers.py              ← Date parsing, number parsing
│   │   └── rules_engine.py         ← Rule evaluation and transaction saving
│   ├── templates/
│   │   └── index.html              ← Single-page HTML shell
│   └── static/
│       ├── css/style.css           ← Full app styling (dark/light themes)
│       └── js/app.js               ← Frontend logic (~2000 lines, vanilla JS)
├── tests/                          ← 156 tests across 8 files
│   ├── conftest.py                 ← Fixtures, helpers, sample CSV data
│   ├── test_bank_detection.py      ← Bank YAML detection (10 banks + cross-check)
│   ├── test_categories.py          ← Category CRUD and cascading
│   ├── test_import_export.py       ← Import, export, round-trip, backup/restore
│   ├── test_rules.py               ← Import rules CRUD and evaluation
│   ├── test_security.py            ← CSRF, path traversal, input validation
│   ├── test_settings.py            ← Budgets, learned merchants, settings
│   ├── test_summary.py             ← Summary, year, averages, recurring
│   └── test_transactions.py        ← CRUD, search, bulk actions, account filter
└── finance.db                      ← Your data (auto-created, gitignored)
```

---

## Adding a new bank

### Option 1: Use the CSV wizard (no code needed)

Drop an unrecognized CSV into the import tab → the wizard opens → map columns → name the bank → save. A YAML config is created in `banks/` and future imports auto-detect.

### Option 2: Write a YAML config manually

Create a file in `banks/` following this pattern:

```yaml
name: "My Bank (Chequing)"
version: 1
last_verified: "2026-04"
account_label: "My Bank Chequing"
encoding: "utf-8-sig"

detection:
  header_contains:
    - "some_unique_header"

columns:
  date: "Date"
  description: "Description"
  debit: "Withdrawals"
  credit: "Deposits"

date_formats:
  - "%m/%d/%Y"
  - "%Y-%m-%d"
```

See existing configs in `banks/` for examples of single-amount vs. debit/credit, flexible column matching, memo fields, description fallbacks, etc.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/months` | List months with data |
| GET | `/api/summary?month=` | Monthly dashboard data |
| GET | `/api/year/<year>` | Year in review |
| GET | `/api/averages` | Monthly category averages |
| GET | `/api/recurring` | Recurring transaction detection |
| GET | `/api/transactions` | List/filter/search transactions |
| GET | `/api/accounts` | List distinct bank accounts |
| POST | `/api/add` | Add a manual transaction |
| PATCH | `/api/update/<id>` | Update a transaction |
| DELETE | `/api/delete/<id>` | Delete a transaction |
| PATCH | `/api/transactions/<id>/hide` | Hide a transaction |
| PATCH | `/api/transactions/<id>/unhide` | Unhide a transaction |
| POST | `/api/bulk-delete` | Delete multiple transactions |
| POST | `/api/bulk-categorize` | Categorize multiple transactions |
| POST | `/api/bulk-hide` | Hide multiple transactions |
| POST | `/api/import` | Import CSV files |
| POST | `/api/detect-csv` | Detect bank from CSV header |
| POST | `/api/save-bank-config` | Save custom bank config |
| POST | `/api/preview-parse` | Preview CSV parsing |
| GET | `/api/export` | Export transactions as CSV |
| GET | `/api/backup` | Download database backup |
| POST | `/api/restore` | Restore from backup |
| GET/POST | `/api/budgets` | Get/set budget limits |
| GET/POST | `/api/settings` | Get/set app settings |
| GET | `/api/categories` | List categories |
| POST | `/api/categories` | Add category |
| PATCH | `/api/categories/<id>` | Rename category |
| DELETE | `/api/categories/<id>` | Delete category |
| GET | `/api/learned` | List learned merchants |
| DELETE | `/api/learned/<keyword>` | Delete learned merchant |
| GET/POST | `/api/rules` | Get/create import rules |
| PATCH | `/api/rules/<id>` | Update rule |
| DELETE | `/api/rules/<id>` | Delete rule |
| POST | `/api/rules/reorder` | Reorder rule priorities |
| POST | `/api/rules/test` | Test rule against existing data |
| POST | `/api/rules/apply-all` | Apply all rules retroactively |
| GET | `/api/rule-templates` | List rule templates |
| POST | `/api/rule-templates/load` | Load a rule template |

---

## Tech Stack

- **Backend:** Python 3.9+ / Flask 3.0+
- **Database:** SQLite (zero config, single file)
- **Frontend:** Vanilla HTML/CSS/JS — no build step, no npm, no framework
- **Charts:** Chart.js (loaded from CDN)
- **Bank configs:** YAML files — easy to add/modify
- **Security:** CSRF protection, SHA-256 hashing, path traversal guards, input validation
- **Tests:** pytest — 156 tests, 8 files, covers every endpoint
- **Total install size:** ~2 MB

---

## Contributing

Issues and PRs welcome. Please don't commit any real transaction data.

To run tests:
```bash
pip install -e ".[dev]"
pytest -v
```

---

## License

MIT
