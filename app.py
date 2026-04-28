#!/usr/bin/env python3
"""
CanadaFinance — Personal Finance Dashboard for Canadians
Run with: python app.py
Then open: http://localhost:5000

Supported banks (CSV import):
  - Tangerine (Chequing + Credit Card)
  - Wealthsimple (Chequing)
  - TD (EasyWeb Chequing CSV)
  - RBC (Online Banking CSV)
  - CIBC (Online Banking CSV)
  - Scotiabank (Online Banking CSV)
  - BMO (Online Banking CSV)
  - National Bank (CSV)
"""

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from flask import Flask, g, jsonify, render_template_string, request, Response

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "finance.db")

# ── DATABASE ──────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('Income','Expense')),
                name        TEXT NOT NULL,
                category    TEXT NOT NULL,
                amount      REAL NOT NULL CHECK(amount > 0),
                account     TEXT NOT NULL,
                notes       TEXT DEFAULT '',
                source      TEXT DEFAULT 'manual',
                tx_hash     TEXT UNIQUE
            );
            CREATE INDEX IF NOT EXISTS idx_date ON transactions(date);
            CREATE INDEX IF NOT EXISTS idx_type ON transactions(type);
            CREATE INDEX IF NOT EXISTS idx_category ON transactions(category);

            CREATE TABLE IF NOT EXISTS learned_merchants (
                keyword     TEXT PRIMARY KEY,
                category    TEXT NOT NULL,
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS budgets (
                category    TEXT PRIMARY KEY,
                monthly_limit REAL NOT NULL CHECK(monthly_limit > 0)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL
            );
        """)
        # Default settings
        db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('theme','dark')")
        db.commit()

def tx_hash(date_str, name, amount, account):
    key = f"{date_str}|{name}|{amount:.2f}|{account}"
    return hashlib.md5(key.encode()).hexdigest()

def get_setting(key, default=""):
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

# ── CATEGORIES ────────────────────────────────────────────────────────────────

EXPENSE_CATS = [
    "Eating Out", "Groceries", "Fuel", "Transport", "Entertainment",
    "Subscriptions", "Healthcare", "Pharmacy", "Clothing", "Shopping",
    "Home", "Insurance", "Travel", "Education", "Phone", "Internet",
    "Utilities", "Car Payment", "Rent", "Savings Transfer", "Misc",
]
INCOME_CATS = ["Job", "Freelance", "Bonus", "Refund", "Other Income"]

CATEGORY_RULES = {
    "Subscriptions": [
        "claude.ai","anthropic","netflix","spotify","apple.com/bill","google one",
        "microsoft 365","adobe","notion","chatgpt","openai","dropbox","icloud",
        "youtube premium","duolingo","amazon prime","prime video",
    ],
    "Fuel": [
        "shell","esso","petro-canada","petro canada","ultramar","pioneer","irving",
        "suncor","husky","pronto","gas station","circle k","couche tard",
        "shefield","sheffield","7-eleven fuel","costco gas",
    ],
    "Groceries": [
        "loblaws","no frills","sobeys","metro","food basics","freshco","farm boy",
        "whole foods","costco wholesale","superstore","real canadian","t&t","maxi",
        "provigo","iga","safeway","save on food","independent","freshmart",
        "grocery","supermarche","epicerie","wmt suprctr","wal-mart","walmart",
    ],
    "Pharmacy": [
        "shoppers drug","rexall","pharmasave","jean coutu","uniprix","proxim",
        "guardian","london drugs","pharmacy","drug mart","supplement","vitamin",
    ],
    "Healthcare": [
        "physio","dentist","dental","doctor","clinic","optometrist","medical",
        "hospital","lab","diagnosis","diagnostics","planet fitness","goodlife",
        "anytime fitness","gym","yoga","pilates","abc*planet","massage","therapy",
    ],
    "Phone": [
        "fido","koodo","public mobile","lucky mobile","virgin mobile",
        "bell mobility","telus mobile","rogers mobile","freedom mobile","chatr",
    ],
    "Internet": [
        "bell internet","rogers internet","videotron","shaw","eastlink","cogeco",
        "teksavvy","distributel",
    ],
    "Utilities": [
        "hydro ottawa","hydro one","bc hydro","enbridge","union gas",
        "atco gas","fortis","electric","water bill","toronto hydro",
    ],
    "Clothing": [
        "winners","marshalls","sport chek","atmosphere","nike","adidas",
        "h&m","zara","uniqlo","old navy","gap","aritzia","lululemon",
        "simons","the bay","hudson's bay","nordstrom","reitmans","ssense","roots",
    ],
    "Home": [
        "ikea","canadian tire","home depot","rona","home hardware",
        "wayfair","structube","article","restoration hardware","pottery barn",
    ],
    "Insurance": [
        "insurance","intact","aviva","state farm","belairdirect","wawanesa",
        "td insurance","rbc insurance","allstate","cooperators","desjardins insur",
    ],
    "Travel": [
        "airbnb","hotel","expedia","booking.com","air canada","westjet","porter",
        "swoop","flair","vrbo","marriott","hilton","delta hotel","best western",
        "kayak","hostel","motel","resort","via rail",
    ],
    "Education": [
        "carleton","university","college","textbook","udemy","coursera",
        "linkedin learn","skillshare","pluralsight","tuition","osap","bookstore",
        "mcgill","uoft","ubc","western university","queens university",
    ],
    "Entertainment": [
        "steam","epic games","xbox","playstation","nintendo","cineplex","landmark",
        "google play","disney+","twitch","riot games","crave","tidal","deezer",
        "gaming","movie","theatre","concert","ticketmaster","eventbrite",
        "billetterie","lcbo","rao #","liquor store","beer store","saq",
        "lotto","lottery",
    ],
    "Transport": [
        "uber","lyft","oc transpo","ttc","stm","translink","presto","parking",
        "taxi","transit","impark","indigo park","greyhound","flixbus","train",
        "enterprise rent","budget rent","hertz","avis","zipcar",
    ],
    "Eating Out": [
        "mcdonald","tim horton","subway","starbucks","uber eat","skip the dishes",
        "doordash","pizza","burger","wendy","kfc","taco bell","harvey's","a&w",
        "mary brown","popeye","chipotle","freshii","pita pit","swiss chalet",
        "boston pizza","jack astor","milestones","cactus club","earls","montana",
        "st-hubert","five guys","nandos","pho","sushi","thai","domino",
        "papa john","little caesar","pizza pizza","pizza hut","hero burger",
        "mucho burrito","shawarma","falafel","osmow","6ixty wing","happy lamb",
        "burrito","chick-fil","dairy queen","d spot","vietnamese","restaurant",
        "cafe","coffee","bakery","diner","bar","pub","grill","kitchen","bistro",
        "eatery","food court","hot pot","wing","ramen","poke","bubble tea",
        "moxie","denny","ihop","east side mario","the keg","joey","menchie",
    ],
    "Shopping": [
        "amazon","target","ebay","etsy","aliexpress","shein","best buy",
        "staples","the source","indigo","chapters","paypal","shopify",
        "dollarama","dollar tree","giant tiger","tanger outlet","rfbt",
        "homesense","apple store","samsung","microsoft store","dell",
    ],
    "Misc": [
        "detail my ride","car wash","car detail","auto detail","dry clean",
        "laundromat","post office","fedex","ups","purolator","canada post",
    ],
}

def categorize(name: str, learned: dict = None) -> str:
    n = name.lower().strip()
    # Hard overrides first
    if "costco gas" in n:
        return "Fuel"
    # User-learned merchants (highest priority)
    if learned:
        for keyword, cat in learned.items():
            if keyword in n:
                return cat
    # Rule-based (check specific categories before generic ones)
    priority_order = [
        "Subscriptions", "Fuel", "Groceries", "Pharmacy", "Healthcare",
        "Phone", "Internet", "Utilities", "Clothing", "Home", "Insurance",
        "Travel", "Education", "Entertainment", "Transport", "Eating Out",
        "Shopping", "Misc",
    ]
    for cat in priority_order:
        for kw in CATEGORY_RULES.get(cat, []):
            if kw in n:
                return cat
    return "UNCATEGORIZED"

def load_learned_dict(db) -> dict:
    rows = db.execute("SELECT keyword, category FROM learned_merchants").fetchall()
    return {r["keyword"]: r["category"] for r in rows}

# ── DATE PARSING ──────────────────────────────────────────────────────────────

def parse_date(raw: str) -> str:
    raw = raw.strip().replace("/", "-")
    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%d-%m-%Y", "%b %d %Y",
                "%B %d %Y", "%d %b %Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")

def safe_float(raw: str) -> float:
    cleaned = re.sub(r"[,$\s]", "", raw.strip())
    cleaned = cleaned.lstrip("-")  # remove sign, we handle direction separately
    return float(cleaned) if cleaned else 0.0

# ── BANK DETECTION ────────────────────────────────────────────────────────────

def detect_bank(header: str) -> str:
    h = header.strip().lower()
    # Wealthsimple — unique underscore-delimited header
    if "transaction_date" in h and "net_cash_amount" in h:
        return "wealthsimple"
    # National Bank (French headers)
    if "date de transaction" in h or ("débit" in h and "crédit" in h):
        return "national_bank"
    # Tangerine Credit — has memo + name + starts with "transaction date"
    if h.startswith("transaction date,") and "name" in h and "memo" in h:
        return "tangerine_credit"
    # CIBC — starts with "transaction date" but has withdrawals (not memo/name)
    if h.startswith("transaction date,") and "withdrawals" in h:
        return "cibc"
    # Tangerine Debit — date, transaction, name, memo
    if h.startswith("date,") and "transaction" in h and "name" in h and "memo" in h:
        return "tangerine_debit"
    # RBC — date + debit + credit + transaction columns
    if h.startswith("date,") and "debit" in h and "credit" in h and "transaction" in h:
        return "rbc"
    # TD — withdrawals with dollar sign in header, or "total balance"
    if ("withdrawals ($)" in h or "total balance" in h) and "deposits" in h:
        return "td"
    # BMO — date + withdrawals + deposits, no transaction col
    if h.startswith("date,") and "withdrawals" in h and "deposits" in h:
        return "bmo"
    # Scotiabank — simple date + description + amount (3 cols)
    if h.startswith("date,") and "description" in h and "amount" in h and "withdrawal" not in h:
        return "scotiabank"
    return "unknown"

# ── PARSERS ───────────────────────────────────────────────────────────────────

def parse_tangerine_debit(text: str, learned: dict) -> list:
    """Import all Tangerine chequing transactions: debits as Expense, credits as Income."""
    txns = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            amount = float(row.get("Amount", 0))
            if amount == 0:
                continue
            desc = row.get("Name", "").strip()
            memo = row.get("Memo", "").strip()
            if memo:
                desc = f"{desc} — {memo}"
            dt = parse_date(row["Date"])
            if amount < 0:
                txns.append({"date": dt, "type": "Expense", "name": desc,
                    "category": categorize(desc, learned), "amount": abs(amount),
                    "account": "Tangerine Chequing", "notes": "", "source": "csv"})
            else:
                cat = categorize(desc, learned)
                if cat == "UNCATEGORIZED":
                    cat = "Other Income"
                txns.append({"date": dt, "type": "Income", "name": desc,
                    "category": cat, "amount": amount,
                    "account": "Tangerine Chequing", "notes": "", "source": "csv"})
        except Exception:
            continue
    return txns

def parse_tangerine_credit(text: str, learned: dict) -> list:
    txns = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            amount = float(row.get("Amount", 0))
            if amount == 0:
                continue
            desc = row.get("Name", "").strip()
            dt = parse_date(row["Transaction date"])
            if amount < 0:
                txns.append({"date": dt, "type": "Expense", "name": desc,
                    "category": categorize(desc, learned), "amount": abs(amount),
                    "account": "Tangerine Credit Card", "notes": "", "source": "csv"})
            else:
                cat = categorize(desc, learned)
                if cat == "UNCATEGORIZED":
                    cat = "Refund"
                txns.append({"date": dt, "type": "Income", "name": desc,
                    "category": cat, "amount": amount,
                    "account": "Tangerine Credit Card", "notes": "", "source": "csv"})
        except Exception:
            continue
    return txns

def parse_wealthsimple(text: str, learned: dict) -> list:
    """Import all Wealthsimple transactions: credits as Income, debits as Expense."""
    txns = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            raw = row.get("net_cash_amount", "")
            if not raw or raw.strip() == "":
                continue
            amount = float(raw)
            if amount == 0:
                continue
            acct = row.get("account_type", "Chequing").strip()
            desc = row.get("description", "").strip()
            if not desc:
                sub = row.get("activity_sub_type", "").strip()
                desc = sub if sub else row.get("activity_type", "Transaction").strip()
            dt = parse_date(row["transaction_date"])
            if amount > 0:
                cat = categorize(desc, learned)
                if cat == "UNCATEGORIZED":
                    cat = "Other Income"
                txns.append({"date": dt, "type": "Income", "name": desc,
                    "category": cat, "amount": amount,
                    "account": f"Wealthsimple {acct}", "notes": "", "source": "csv"})
            else:
                txns.append({"date": dt, "type": "Expense", "name": desc,
                    "category": categorize(desc, learned), "amount": abs(amount),
                    "account": f"Wealthsimple {acct}", "notes": "", "source": "csv"})
        except Exception:
            continue
    return txns

def parse_td(text: str, learned: dict) -> list:
    """TD EasyWeb chequing CSV: Date,Description,Withdrawals ($),Deposits ($),Total Balance ($)"""
    txns = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            # Find withdrawal and deposit columns flexibly
            keys = list(row.keys())
            w_key = next((k for k in keys if "withdrawal" in k.lower()), None)
            d_key = next((k for k in keys if "deposit" in k.lower()), None)
            desc_key = next((k for k in keys if "description" in k.lower()), None)
            date_key = next((k for k in keys if k.lower() == "date"), None)
            if not all([w_key, d_key, desc_key, date_key]):
                continue
            w = safe_float(row[w_key]) if row[w_key].strip() else 0
            d = safe_float(row[d_key]) if row[d_key].strip() else 0
            desc = row[desc_key].strip()
            dt = parse_date(row[date_key])
            if w > 0:
                txns.append({"date": dt, "type": "Expense", "name": desc,
                    "category": categorize(desc, learned), "amount": w,
                    "account": "TD Chequing", "notes": "", "source": "csv"})
            elif d > 0:
                txns.append({"date": dt, "type": "Income", "name": desc,
                    "category": categorize(desc, learned), "amount": d,
                    "account": "TD Chequing", "notes": "", "source": "csv"})
        except Exception:
            continue
    return txns

def parse_rbc(text: str, learned: dict) -> list:
    """RBC CSV: Date,Description,Transaction,Debit,Credit,Total"""
    txns = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            desc = row.get("Description", "").strip()
            dt = parse_date(row.get("Date", ""))
            debit_raw = row.get("Debit", "").strip()
            credit_raw = row.get("Credit", "").strip()
            if debit_raw:
                amt = safe_float(debit_raw)
                if amt > 0:
                    txns.append({"date": dt, "type": "Expense", "name": desc,
                        "category": categorize(desc, learned), "amount": amt,
                        "account": "RBC Chequing", "notes": "", "source": "csv"})
            elif credit_raw:
                amt = safe_float(credit_raw)
                if amt > 0:
                    txns.append({"date": dt, "type": "Income", "name": desc,
                        "category": categorize(desc, learned), "amount": amt,
                        "account": "RBC Chequing", "notes": "", "source": "csv"})
        except Exception:
            continue
    return txns

def parse_cibc(text: str, learned: dict) -> list:
    """CIBC CSV: Transaction Date,Description,Withdrawals,Deposits,Balance"""
    txns = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            keys = {k.lower().strip(): k for k in row.keys()}
            date_key = keys.get("transaction date") or keys.get("date")
            desc_key = keys.get("description")
            w_key = keys.get("withdrawals")
            d_key = keys.get("deposits")
            if not all([date_key, desc_key, w_key, d_key]):
                continue
            desc = row[desc_key].strip()
            dt = parse_date(row[date_key])
            w = safe_float(row[w_key]) if row[w_key].strip() else 0
            d = safe_float(row[d_key]) if row[d_key].strip() else 0
            if w > 0:
                txns.append({"date": dt, "type": "Expense", "name": desc,
                    "category": categorize(desc, learned), "amount": w,
                    "account": "CIBC Chequing", "notes": "", "source": "csv"})
            elif d > 0:
                txns.append({"date": dt, "type": "Income", "name": desc,
                    "category": categorize(desc, learned), "amount": d,
                    "account": "CIBC Chequing", "notes": "", "source": "csv"})
        except Exception:
            continue
    return txns

def parse_scotiabank(text: str, learned: dict) -> list:
    """Scotiabank CSV: Date,Description,Amount (negative=debit, positive=credit)"""
    txns = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            amt_raw = row.get("Amount", row.get("Transactions", "")).strip()
            amt = float(re.sub(r"[,$\s]", "", amt_raw))
            desc = row.get("Description", row.get("Payee", "")).strip()
            dt = parse_date(row.get("Date", ""))
            if amt < 0:
                txns.append({"date": dt, "type": "Expense", "name": desc,
                    "category": categorize(desc, learned), "amount": abs(amt),
                    "account": "Scotiabank", "notes": "", "source": "csv"})
            elif amt > 0:
                txns.append({"date": dt, "type": "Income", "name": desc,
                    "category": categorize(desc, learned), "amount": amt,
                    "account": "Scotiabank", "notes": "", "source": "csv"})
        except Exception:
            continue
    return txns

def parse_bmo(text: str, learned: dict) -> list:
    """BMO CSV: Date,Description,Withdrawals,Deposits,Balance"""
    txns = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            keys = {k.lower().strip(): k for k in row.keys()}
            desc_key = keys.get("description") or keys.get("payee")
            date_key = keys.get("date")
            w_key = next((v for k,v in keys.items() if "withdrawal" in k), None)
            d_key = next((v for k,v in keys.items() if "deposit" in k), None)
            if not all([date_key, desc_key]):
                continue
            desc = row[desc_key].strip()
            dt = parse_date(row[date_key])
            w = safe_float(row[w_key]) if w_key and row[w_key].strip() else 0
            d = safe_float(row[d_key]) if d_key and row[d_key].strip() else 0
            if w > 0:
                txns.append({"date": dt, "type": "Expense", "name": desc,
                    "category": categorize(desc, learned), "amount": w,
                    "account": "BMO Chequing", "notes": "", "source": "csv"})
            elif d > 0:
                txns.append({"date": dt, "type": "Income", "name": desc,
                    "category": categorize(desc, learned), "amount": d,
                    "account": "BMO Chequing", "notes": "", "source": "csv"})
        except Exception:
            continue
    return txns

def parse_national_bank(text: str, learned: dict) -> list:
    """National Bank CSV (bilingual): Date,Description,Debit/Débit,Credit/Crédit,Balance"""
    txns = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            keys = {k.lower().strip(): k for k in row.keys()}
            date_key = next((v for k,v in keys.items() if "date" in k), None)
            desc_key = next((v for k,v in keys.items() if "description" in k or "libellé" in k), None)
            d_key = next((v for k,v in keys.items() if "débit" in k or "debit" in k), None)
            c_key = next((v for k,v in keys.items() if "crédit" in k or "credit" in k), None)
            if not all([date_key, desc_key]):
                continue
            desc = row[desc_key].strip()
            dt = parse_date(row[date_key])
            d = safe_float(row[d_key]) if d_key and row.get(d_key, "").strip() else 0
            c = safe_float(row[c_key]) if c_key and row.get(c_key, "").strip() else 0
            if d > 0:
                txns.append({"date": dt, "type": "Expense", "name": desc,
                    "category": categorize(desc, learned), "amount": d,
                    "account": "National Bank", "notes": "", "source": "csv"})
            elif c > 0:
                txns.append({"date": dt, "type": "Income", "name": desc,
                    "category": categorize(desc, learned), "amount": c,
                    "account": "National Bank", "notes": "", "source": "csv"})
        except Exception:
            continue
    return txns

def parse_csv_text(text: str, learned: dict = None) -> tuple:
    if learned is None:
        learned = {}
    first_line = text.splitlines()[0] if text.strip() else ""
    bank = detect_bank(first_line)
    parsers = {
        "tangerine_debit":  lambda: parse_tangerine_debit(text, learned),
        "tangerine_credit": lambda: parse_tangerine_credit(text, learned),
        "wealthsimple":     lambda: parse_wealthsimple(text, learned),
        "td":               lambda: parse_td(text, learned),
        "rbc":              lambda: parse_rbc(text, learned),
        "cibc":             lambda: parse_cibc(text, learned),
        "scotiabank":       lambda: parse_scotiabank(text, learned),
        "bmo":              lambda: parse_bmo(text, learned),
        "national_bank":    lambda: parse_national_bank(text, learned),
    }
    fn = parsers.get(bank)
    return (fn() if fn else []), bank

def save_transactions(txns: list) -> tuple:
    added = dupes = 0
    with sqlite3.connect(DB_PATH) as db:
        for t in txns:
            h = tx_hash(t["date"], t["name"], t["amount"], t["account"])
            try:
                db.execute("""INSERT INTO transactions
                    (date,type,name,category,amount,account,notes,source,tx_hash)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (t["date"], t["type"], t["name"], t["category"],
                     t["amount"], t["account"], t.get("notes",""), t.get("source","csv"), h))
                added += 1
            except sqlite3.IntegrityError:
                dupes += 1
        db.commit()
    return added, dupes

# ── API ROUTES ────────────────────────────────────────────────────────────────

@app.route("/api/months")
def api_months():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT substr(date,1,7) as m FROM transactions ORDER BY m DESC"
    ).fetchall()
    return jsonify([r["m"] for r in rows])

@app.route("/api/summary")
def api_summary():
    month = request.args.get("month", "")
    db = get_db()
    like = f"{month}%"
    income = db.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Income' AND date LIKE ?", (like,)
    ).fetchone()["t"]
    expenses = db.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND date LIKE ?", (like,)
    ).fetchone()["t"]
    by_cat = db.execute(
        """SELECT category, SUM(amount) as total FROM transactions
           WHERE type='Expense' AND date LIKE ? GROUP BY category ORDER BY total DESC""", (like,)
    ).fetchall()
    income_by_cat = db.execute(
        """SELECT category, SUM(amount) as total FROM transactions
           WHERE type='Income' AND date LIKE ? GROUP BY category ORDER BY total DESC""", (like,)
    ).fetchall()
    # Previous month for comparison
    if month:
        y, m = int(month[:4]), int(month[5:7])
        pm = date(y, m, 1) - timedelta(days=1)
        prev_like = f"{pm.year}-{pm.month:02d}%"
        prev_exp = db.execute(
            "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND date LIKE ?", (prev_like,)
        ).fetchone()["t"]
        prev_by_cat = db.execute(
            """SELECT category, SUM(amount) as total FROM transactions
               WHERE type='Expense' AND date LIKE ? GROUP BY category""", (prev_like,)
        ).fetchall()
        prev_cat_map = {r["category"]: r["total"] for r in prev_by_cat}
    else:
        prev_exp = 0
        prev_cat_map = {}
    # Budgets
    budgets = {r["category"]: r["monthly_limit"] for r in
               db.execute("SELECT category, monthly_limit FROM budgets").fetchall()}
    by_cat_out = []
    for r in by_cat:
        cat = r["category"]
        by_cat_out.append({
            "category": cat, "total": r["total"],
            "prev_total": prev_cat_map.get(cat, 0),
            "budget": budgets.get(cat),
        })
    return jsonify({
        "income": income, "expenses": expenses, "net": income - expenses,
        "prev_expenses": prev_exp,
        "savings_rate": round((income - expenses) / income * 100, 1) if income > 0 else 0,
        "by_category": by_cat_out,
        "income_by_category": [{"category": r["category"], "total": r["total"]} for r in income_by_cat],
    })

@app.route("/api/transactions")
def api_transactions():
    month  = request.args.get("month", "")
    cat    = request.args.get("category", "")
    typ    = request.args.get("type", "")
    search = request.args.get("search", "").strip()
    db     = get_db()
    if search:
        term = f"%{search}%"
        q = """SELECT * FROM transactions WHERE
               (name LIKE ? OR category LIKE ? OR account LIKE ? OR notes LIKE ? OR date LIKE ?)"""
        params = [term]*5
        if typ: q += " AND type=?"; params.append(typ)
        q += " ORDER BY date DESC, id DESC"
    else:
        q = "SELECT * FROM transactions WHERE date LIKE ?"
        params = [f"{month}%"]
        if cat: q += " AND category=?"; params.append(cat)
        if typ: q += " AND type=?"; params.append(typ)
        q += " ORDER BY date DESC, id DESC"
    rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/add", methods=["POST"])
def api_add():
    d = request.json
    for f in ["date","type","name","category","amount","account"]:
        if not d.get(f): return jsonify({"error": f"Missing: {f}"}), 400
    try:
        amount = float(d["amount"])
        h = tx_hash(d["date"], d["name"], amount, d["account"])
        get_db().execute("""INSERT INTO transactions
            (date,type,name,category,amount,account,notes,source,tx_hash)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (d["date"], d["type"], d["name"], d["category"],
             amount, d["account"], d.get("notes",""), "manual", h))
        get_db().commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Duplicate transaction"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/update/<int:tid>", methods=["PATCH"])
def api_update(tid):
    d = request.json
    allowed = ["date","type","name","category","amount","account","notes"]
    sets = ", ".join(f"{k}=?" for k in d if k in allowed)
    vals = [d[k] for k in d if k in allowed] + [tid]
    if not sets: return jsonify({"error": "Nothing to update"}), 400
    db = get_db()
    db.row_factory = sqlite3.Row
    original = db.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    db.execute(f"UPDATE transactions SET {sets} WHERE id=?", vals)
    retro_fixed = 0
    if "category" in d and original:
        new_cat = d["category"]
        orig_name = original["name"].lower().strip()
        db.execute("""INSERT INTO learned_merchants (keyword, category) VALUES (?,?)
            ON CONFLICT(keyword) DO UPDATE SET category=excluded.category, updated_at=datetime('now')
        """, (orig_name, new_cat))
        all_learned = db.execute("SELECT keyword, category FROM learned_merchants").fetchall()
        for row in db.execute("SELECT id, name FROM transactions WHERE category='UNCATEGORIZED'").fetchall():
            rn = row["name"].lower()
            for lrow in all_learned:
                words = [w for w in lrow["keyword"].split() if len(w) > 3]
                if any(w in rn for w in words):
                    db.execute("UPDATE transactions SET category=? WHERE id=?", (lrow["category"], row["id"]))
                    retro_fixed += 1
                    break
    db.commit()
    return jsonify({"ok": True, "retro_fixed": retro_fixed})

@app.route("/api/delete/<int:tid>", methods=["DELETE"])
def api_delete(tid):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id=?", (tid,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/import", methods=["POST"])
def api_import():
    db = get_db()
    learned = load_learned_dict(db)
    results = []
    for f in request.files.getlist("files"):
        text = f.read().decode("utf-8-sig")
        txns, bank = parse_csv_text(text, learned)
        added, dupes = save_transactions(txns)
        results.append({"file": f.filename, "bank": bank, "added": added, "dupes": dupes})
    return jsonify(results)

@app.route("/api/export")
def api_export():
    month = request.args.get("month", "")
    db = get_db()
    q = "SELECT date,type,name,category,amount,account,notes,source FROM transactions"
    params = []
    if month:
        q += " WHERE date LIKE ?"; params.append(f"{month}%")
    q += " ORDER BY date DESC"
    rows = db.execute(q, params).fetchall()
    def generate():
        yield "Date,Type,Name,Category,Amount,Account,Notes,Source\n"
        for r in rows:
            yield ",".join(f'"{str(v)}"' for v in r) + "\n"
    filename = f"transactions_{month or 'all'}.csv"
    return Response(generate(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.route("/api/year/<int:year>")
def api_year(year):
    db = get_db()
    months_data = []
    for m in range(1, 13):
        like = f"{year}-{m:02d}%"
        inc = db.execute("SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Income' AND date LIKE ?", (like,)).fetchone()["t"]
        exp = db.execute("SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND date LIKE ?", (like,)).fetchone()["t"]
        months_data.append({"month": f"{year}-{m:02d}", "income": inc, "expenses": exp, "net": inc-exp})
    top_cats = db.execute("""
        SELECT category, SUM(amount) as total FROM transactions
        WHERE type='Expense' AND date LIKE ? GROUP BY category ORDER BY total DESC LIMIT 5
    """, (f"{year}%",)).fetchall()
    return jsonify({
        "months": months_data,
        "top_categories": [{"category": r["category"], "total": r["total"]} for r in top_cats],
        "total_income": sum(m["income"] for m in months_data),
        "total_expenses": sum(m["expenses"] for m in months_data),
    })

@app.route("/api/budgets", methods=["GET"])
def api_budgets_get():
    db = get_db()
    rows = db.execute("SELECT category, monthly_limit FROM budgets").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/budgets", methods=["POST"])
def api_budgets_set():
    d = request.json
    db = get_db()
    db.execute("""INSERT INTO budgets (category, monthly_limit) VALUES (?,?)
        ON CONFLICT(category) DO UPDATE SET monthly_limit=excluded.monthly_limit
    """, (d["category"], float(d["amount"])))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/budgets/<string:cat>", methods=["DELETE"])
def api_budgets_del(cat):
    db = get_db()
    db.execute("DELETE FROM budgets WHERE category=?", (cat,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/learned")
def api_learned():
    db = get_db()
    rows = db.execute("SELECT keyword, category, updated_at FROM learned_merchants ORDER BY updated_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/learned/<path:keyword>", methods=["DELETE"])
def api_learned_del(keyword):
    db = get_db()
    db.execute("DELETE FROM learned_merchants WHERE keyword=?", (keyword,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return jsonify({r["key"]: r["value"] for r in rows})

@app.route("/api/settings", methods=["POST"])
def api_settings_set():
    d = request.json
    db = get_db()
    for key, val in d.items():
        db.execute("INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, val))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/averages")
def api_averages():
    """Monthly average spend per category based on last 6 months."""
    db = get_db()
    months_with_data = db.execute("""
        SELECT DISTINCT substr(date,1,7) as m FROM transactions
        WHERE type='Expense' ORDER BY m DESC LIMIT 6
    """).fetchall()
    n = len(months_with_data)
    if n == 0:
        return jsonify([])
    placeholders = ','.join('?'*n)
    rows = db.execute(f"""
        SELECT category,
               ROUND(SUM(amount)/{n}, 2) as avg_monthly,
               COUNT(DISTINCT substr(date,1,7)) as months_seen
        FROM transactions WHERE type='Expense'
        AND substr(date,1,7) IN ({placeholders})
        GROUP BY category ORDER BY avg_monthly DESC
    """, [r['m'] for r in months_with_data]).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/")
def index():
    return render_template_string(HTML)

# ── HTML / CSS / JS ───────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CanadaFinance</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {
  --bg:#0e0f11; --surface:#16181c; --surface2:#1e2128; --border:#2a2d35;
  --text:#e8eaf0; --muted:#6b7280; --accent:#6ee7b7; --red:#f87171;
  --blue:#60a5fa; --purple:#a78bfa; --amber:#f59e0b;
  --mono:'DM Mono',monospace; --sans:'DM Sans',sans-serif;
  --radius:12px;
}
[data-theme=light] {
  --bg:#f8f9fa; --surface:#ffffff; --surface2:#f1f3f5; --border:#dee2e6;
  --text:#212529; --muted:#868e96;
}
*{box-sizing:border-box;margin:0;padding:0}
html{font-size:14px}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh;transition:background .2s,color .2s}

/* Layout */
.shell{display:flex;min-height:100vh}
.sidebar{width:230px;background:var(--surface);border-right:1px solid var(--border);
  padding:24px 16px;display:flex;flex-direction:column;gap:4px;flex-shrink:0;
  position:sticky;top:0;height:100vh;overflow-y:auto}
.main{flex:1;padding:28px 32px;overflow-x:hidden;max-width:1200px}

/* Sidebar */
.logo{font-family:var(--mono);font-size:12px;color:var(--accent);letter-spacing:2px;
  text-transform:uppercase;margin-bottom:24px;padding-bottom:14px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:8px}
.logo-icon{font-size:18px}
.nav-label{font-size:10px;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;
  margin:14px 0 4px 8px;font-family:var(--mono)}
.nav-btn{background:none;border:none;color:var(--muted);font-family:var(--sans);font-size:13px;
  padding:8px 12px;border-radius:8px;cursor:pointer;text-align:left;width:100%;
  transition:all .15s;display:flex;align-items:center;gap:9px;line-height:1.3}
.nav-btn:hover{background:var(--surface2);color:var(--text)}
.nav-btn.active{background:var(--surface2);color:var(--accent);font-weight:500}
.nav-btn svg{flex-shrink:0;opacity:.6}
.nav-btn.active svg{opacity:1}
.sidebar-bottom{margin-top:auto;padding-top:12px;border-top:1px solid var(--border)}

/* Month nav */
.month-row{display:flex;align-items:center;gap:10px;margin-bottom:24px}
.month-label{font-family:var(--mono);font-size:18px;font-weight:500;flex:1}
.month-btn{background:var(--surface);border:1px solid var(--border);color:var(--text);
  width:30px;height:30px;border-radius:8px;cursor:pointer;font-size:15px;
  display:flex;align-items:center;justify-content:center;transition:all .15s}
.month-btn:hover{border-color:var(--accent);color:var(--accent)}

/* Cards */
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px}
.card-label{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;
  font-family:var(--mono);margin-bottom:8px}
.card-value{font-family:var(--mono);font-size:22px;font-weight:500}
.card-value.green{color:var(--accent)}
.card-value.red{color:var(--red)}
.card-value.blue{color:var(--blue)}
.card-sub{font-size:11px;color:var(--muted);margin-top:5px;font-family:var(--mono)}
.card-sub.up{color:#4ade80}.card-sub.down{color:var(--red)}

/* Panels */
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:24px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px 22px}
.panel-title{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;
  font-family:var(--mono);margin-bottom:16px;display:flex;align-items:center;justify-content:space-between}

/* Cat list */
.cat-row{display:flex;align-items:center;gap:10px;padding:7px 0;
  border-bottom:1px solid var(--border);cursor:pointer;transition:opacity .15s}
.cat-row:last-child{border:none}
.cat-row:hover{opacity:.8}
.cat-name{flex:1;font-size:13px}
.cat-bar-wrap{width:60px;height:3px;background:var(--border);border-radius:2px}
.cat-bar{height:3px;border-radius:2px;background:var(--accent);transition:width .4s}
.cat-budget{font-size:10px;font-family:var(--mono);color:var(--muted);min-width:32px;text-align:right}
.cat-budget.over{color:var(--red)}
.cat-amt{font-family:var(--mono);font-size:12px;min-width:64px;text-align:right}

/* Budget bar */
.budget-bar-wrap{width:60px;height:3px;background:var(--border);border-radius:2px;overflow:hidden}
.budget-bar{height:3px;border-radius:2px;transition:width .4s}

/* Chart */
.chart-wrap{position:relative;height:200px}

/* Transactions */
.txn-header{display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.txn-title{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;
  font-family:var(--mono);flex:1}
.filter-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
select,input[type=text],input[type=date],input[type=number]{
  background:var(--surface2);border:1px solid var(--border);color:var(--text);
  font-family:var(--sans);font-size:13px;padding:7px 11px;border-radius:8px;outline:none}
select:focus,input:focus{border-color:var(--accent)}

.txn-table{width:100%;border-collapse:collapse}
.txn-table th{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;
  font-family:var(--mono);padding:0 10px 10px;text-align:left;white-space:nowrap}
.txn-table td{padding:10px;border-bottom:1px solid var(--border);font-size:13px;vertical-align:middle}
.txn-table tr:last-child td{border:none}
.txn-table tr:hover td{background:var(--surface2)}
.txn-table tr{cursor:pointer;transition:background .1s}
.badge{display:inline-block;font-size:11px;font-family:var(--mono);padding:2px 8px;
  border-radius:20px;background:var(--surface2);color:var(--muted);white-space:nowrap}
.badge.income{background:rgba(110,231,183,.12);color:var(--accent)}
.badge.expense{background:rgba(248,113,113,.1);color:var(--red)}
.amt-income{font-family:var(--mono);color:var(--accent)}
.amt-expense{font-family:var(--mono);color:var(--red)}
.del-btn{background:none;border:none;color:var(--border);cursor:pointer;font-size:16px;
  padding:2px 5px;border-radius:4px;transition:all .15s;line-height:1}
.del-btn:hover{color:var(--red);background:rgba(248,113,113,.1)}

/* Buttons */
.btn{background:var(--accent);color:#0e0f11;border:none;font-family:var(--sans);
  font-weight:600;font-size:13px;padding:8px 16px;border-radius:8px;cursor:pointer;transition:all .15s}
.btn:hover{opacity:.85}
.btn-ghost{background:var(--surface2);color:var(--text);border:1px solid var(--border)}
.btn-ghost:hover{border-color:var(--accent);color:var(--accent)}
.btn-sm{padding:5px 12px;font-size:12px}
.btn-red{background:rgba(248,113,113,.15);color:var(--red);border:1px solid rgba(248,113,113,.3)}
.btn-red:hover{background:rgba(248,113,113,.25)}
.btn-icon{background:none;border:none;cursor:pointer;color:var(--muted);font-size:16px;
  padding:4px 6px;border-radius:6px;transition:all .15s}
.btn-icon:hover{color:var(--text);background:var(--surface2)}

/* Modal */
.modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.65);display:none;
  align-items:center;justify-content:center;z-index:200;backdrop-filter:blur(4px)}
.modal-backdrop.open{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:18px;
  padding:26px 30px;width:480px;max-width:95vw;max-height:90vh;overflow-y:auto}
.modal-title{font-size:15px;font-weight:600;margin-bottom:20px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.form-group{display:flex;flex-direction:column;gap:5px}
.form-group.full{grid-column:1/-1}
label{font-size:10px;color:var(--muted);letter-spacing:.5px;text-transform:uppercase;font-family:var(--mono)}
.form-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:20px}

/* Import */
.drop-zone{border:2px dashed var(--border);border-radius:var(--radius);padding:36px 20px;
  text-align:center;cursor:pointer;transition:all .2s}
.drop-zone:hover,.drop-zone.drag{border-color:var(--accent);background:rgba(110,231,183,.04)}
.drop-zone p{color:var(--muted);font-size:13px;margin-top:6px}
.file-icon{font-size:26px;margin-bottom:4px}
.import-results{margin-top:16px;display:flex;flex-direction:column;gap:6px}
.result-row{background:var(--surface2);border-radius:8px;padding:10px 14px;
  display:flex;align-items:center;gap:10px;font-size:13px}
.result-bank{font-family:var(--mono);font-size:10px;color:var(--muted)}

/* Search banner */
.search-banner{padding:6px 0 12px;font-size:12px;color:var(--muted);font-family:var(--mono)}

/* Settings */
.settings-section{margin-bottom:28px}
.settings-title{font-size:12px;font-weight:600;margin-bottom:12px;color:var(--text)}
.settings-row{display:flex;align-items:center;justify-content:space-between;
  padding:10px 0;border-bottom:1px solid var(--border)}
.settings-row:last-child{border:none}
.settings-label{font-size:13px}
.settings-sub{font-size:11px;color:var(--muted);margin-top:2px}
.tag{display:inline-flex;align-items:center;gap:5px;background:var(--surface2);
  border:1px solid var(--border);border-radius:20px;padding:3px 10px;font-size:12px;
  font-family:var(--mono);margin:2px}
.tag .x{cursor:pointer;color:var(--muted);font-size:14px;line-height:1}
.tag .x:hover{color:var(--red)}

/* Year view */
.year-bar-row{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--border)}
.year-bar-row:last-child{border:none}
.year-month{font-family:var(--mono);font-size:11px;color:var(--muted);width:60px;flex-shrink:0}
.year-bar-wrap{flex:1;display:flex;flex-direction:column;gap:3px}
.year-bar{height:6px;border-radius:3px;transition:width .4s;min-width:2px}
.year-bar.income{background:var(--accent)}
.year-bar.expense{background:var(--red)}
.year-amounts{display:flex;gap:12px;font-family:var(--mono);font-size:11px}

/* Averages panel uses existing cat-row styles */

/* Toast */
.toast{position:fixed;bottom:20px;right:20px;background:var(--surface2);
  border:1px solid var(--border);border-radius:10px;padding:10px 18px;font-size:13px;
  transform:translateY(80px);opacity:0;transition:all .3s;z-index:300;max-width:320px}
.toast.show{transform:translateY(0);opacity:1}
.toast.success{border-color:var(--accent);color:var(--accent)}
.toast.error{border-color:var(--red);color:var(--red)}

/* Sections */
.section{display:none}
.section.active{display:block}
.empty{color:var(--muted);font-size:13px;text-align:center;padding:36px 0;font-family:var(--mono)}

/* Toggle switch */
.toggle{position:relative;width:40px;height:22px}
.toggle input{opacity:0;width:0;height:0}
.toggle-slider{position:absolute;inset:0;background:var(--border);border-radius:22px;cursor:pointer;transition:.3s}
.toggle-slider:before{content:'';position:absolute;width:16px;height:16px;left:3px;bottom:3px;
  background:#fff;border-radius:50%;transition:.3s}
.toggle input:checked + .toggle-slider{background:var(--accent)}
.toggle input:checked + .toggle-slider:before{transform:translateX(18px)}

/* Responsive */
@media(max-width:900px){
  .cards{grid-template-columns:1fr 1fr}
  .grid2{grid-template-columns:1fr}
}
@media(max-width:600px){
  .sidebar{display:none}
  .main{padding:16px}
  .cards{grid-template-columns:1fr}
}
</style>
</head>
<body>
<div class="shell">

<!-- SIDEBAR -->
<aside class="sidebar">
  <div class="logo"><span class="logo-icon">🍁</span>CanadaFinance</div>

  <span class="nav-label">Views</span>
  <button class="nav-btn active" onclick="nav('dashboard')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
    Dashboard
  </button>
  <button class="nav-btn" onclick="nav('transactions')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
    Transactions
  </button>
  <button class="nav-btn" onclick="nav('year')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
    Year Review
  </button>
  <button class="nav-btn" onclick="nav('import')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
    Import CSV
  </button>
  <button class="nav-btn" onclick="nav('settings')">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
    Settings
  </button>

  <span class="nav-label">Actions</span>
  <button class="nav-btn" onclick="openAddModal()">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/></svg>
    Add Transaction
  </button>
  <button class="nav-btn" onclick="exportCSV(false)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
    Export Month
  </button>
  <button class="nav-btn" onclick="exportCSV(true)">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
    Export All
  </button>

  <div class="sidebar-bottom">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0">
      <span style="font-size:12px;color:var(--muted)">Dark mode</span>
      <label class="toggle">
        <input type="checkbox" id="theme-toggle" onchange="toggleTheme()" checked>
        <span class="toggle-slider"></span>
      </label>
    </div>
  </div>
</aside>

<!-- MAIN -->
<main class="main">

<!-- DASHBOARD -->
<section id="sec-dashboard" class="section active">
  <div class="month-row">
    <button class="month-btn" onclick="changeMonth(-1)">←</button>
    <div class="month-label" id="month-display">—</div>
    <button class="month-btn" onclick="changeMonth(1)">→</button>
  </div>
  <div class="cards">
    <div class="card">
      <div class="card-label">Income</div>
      <div class="card-value green" id="card-income">$—</div>
      <div class="card-sub" id="card-income-src">—</div>
    </div>
    <div class="card">
      <div class="card-label">Expenses</div>
      <div class="card-value red" id="card-expense">$—</div>
      <div class="card-sub" id="card-expense-vs">—</div>
    </div>
    <div class="card">
      <div class="card-label">Net Saved</div>
      <div class="card-value" id="card-net">$—</div>
      <div class="card-sub" id="card-net-sub">—</div>
    </div>
    <div class="card">
      <div class="card-label">Savings Rate</div>
      <div class="card-value blue" id="card-rate">—%</div>
      <div class="card-sub" id="card-rate-sub">of income saved</div>
    </div>
  </div>
  <div class="grid2">
    <div class="panel">
      <div class="panel-title">
        Spending by Category
        <button class="btn-icon" title="Set budgets" onclick="nav('settings');showBudgetPanel()">⚙</button>
      </div>
      <div id="cat-list"></div>
    </div>
    <div class="panel">
      <div class="panel-title">Breakdown</div>
      <div class="chart-wrap"><canvas id="donut-chart"></canvas></div>
    </div>
  </div>
  <div class="grid2">
    <div class="panel">
      <div class="panel-title">Monthly Averages <span id="avg-subtitle" style="font-size:10px;color:var(--muted);font-weight:normal"></span></div>
      <div id="averages-list"><div class="empty">Loading…</div></div>
    </div>
    <div class="panel">
      <div class="panel-title">Recent Transactions</div>
      <table class="txn-table">
        <thead><tr><th>Date</th><th>Name</th><th>Category</th><th style="text-align:right">Amount</th></tr></thead>
        <tbody id="recent-txns"></tbody>
      </table>
    </div>
  </div>
</section>

<!-- TRANSACTIONS -->
<section id="sec-transactions" class="section">
  <div class="txn-header">
    <div class="txn-title">All Transactions</div>
    <div class="filter-row">
      <input type="text" id="search-input" placeholder="Search — costco, eating out, 2026-03…"
        style="width:260px" oninput="onSearchInput()" onkeydown="if(event.key==='Escape')clearSearch()">
      <select id="filter-type" onchange="loadTransactions()">
        <option value="">All Types</option>
        <option value="Expense">Expenses</option>
        <option value="Income">Income</option>
      </select>
      <select id="filter-cat" onchange="loadTransactions()"><option value="">All Categories</option></select>
      <button class="btn btn-sm" onclick="openAddModal()">+ Add</button>
    </div>
  </div>
  <div id="search-banner" class="search-banner" style="display:none"></div>
  <table class="txn-table">
    <thead><tr>
      <th>Date</th><th>Name</th><th>Category</th><th>Account</th>
      <th>Type</th><th style="text-align:right">Amount</th><th></th>
    </tr></thead>
    <tbody id="all-txns"></tbody>
  </table>
  <div id="txn-empty" class="empty" style="display:none">No transactions found</div>
</section>

<!-- YEAR REVIEW -->
<section id="sec-year" class="section">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px">
    <button class="month-btn" onclick="changeYear(-1)">←</button>
    <div class="month-label" id="year-display">—</div>
    <button class="month-btn" onclick="changeYear(1)">→</button>
  </div>
  <div class="cards" style="grid-template-columns:repeat(3,1fr)" id="year-cards"></div>
  <div class="grid2">
    <div class="panel">
      <div class="panel-title">Monthly Overview</div>
      <div id="year-bars"></div>
    </div>
    <div class="panel">
      <div class="panel-title">Top 5 Categories</div>
      <div id="year-cats"></div>
    </div>
  </div>
</section>

<!-- IMPORT -->
<section id="sec-import" class="section">
  <div class="panel" style="max-width:580px">
    <div class="panel-title">Import Bank CSVs</div>
    <div class="drop-zone" id="drop-zone" onclick="document.getElementById('csv-input').click()"
      ondragover="event.preventDefault();this.classList.add('drag')"
      ondragleave="this.classList.remove('drag')"
      ondrop="handleDrop(event)">
      <div class="file-icon">📂</div>
      <strong>Drop CSV files here</strong>
      <p>Tangerine · Wealthsimple · TD · RBC · CIBC · Scotiabank · BMO · National Bank</p>
    </div>
    <input type="file" id="csv-input" multiple accept=".csv" style="display:none" onchange="handleFiles(this.files)">
    <div class="import-results" id="import-results"></div>
  </div>
</section>

<!-- SETTINGS -->
<section id="sec-settings" class="section">
  <div style="max-width:600px">

    <div class="settings-section" id="budget-panel">
      <div class="settings-title">Monthly Budgets</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:12px">
        Set spending limits per category. Progress bars appear on the dashboard.
      </p>
      <div id="budget-list" style="margin-bottom:12px"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <select id="budget-cat" style="flex:1;min-width:160px">
          <option value="">Select category…</option>
        </select>
        <input type="number" id="budget-amt" placeholder="$" style="width:100px" min="1">
        <button class="btn btn-sm" onclick="saveBudget()">Set Budget</button>
      </div>
    </div>

    <div class="settings-section">
      <div class="settings-title">Learned Merchants</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:12px">
        Categories you've set manually. Deleted entries revert to auto-categorization.
      </p>
      <div id="learned-list"></div>
    </div>

  </div>
</section>

</main>
</div>

<!-- ADD MODAL -->
<div class="modal-backdrop" id="add-modal">
  <div class="modal">
    <div class="modal-title">Add Transaction</div>
    <div class="form-grid">
      <div class="form-group"><label>Date</label><input type="date" id="f-date"></div>
      <div class="form-group"><label>Type</label>
        <select id="f-type" onchange="updateCatOptions('f-category','f-type')">
          <option value="Expense">Expense</option>
          <option value="Income">Income</option>
        </select>
      </div>
      <div class="form-group full"><label>Name / Description</label>
        <input type="text" id="f-name" placeholder="e.g. Tim Hortons, Dad car payment">
      </div>
      <div class="form-group"><label>Category</label><select id="f-category"></select></div>
      <div class="form-group"><label>Amount ($)</label>
        <input type="number" id="f-amount" step="0.01" min="0" placeholder="0.00">
      </div>
      <div class="form-group"><label>Account</label>
        <select id="f-account">
          <option>Tangerine Credit Card</option><option>Tangerine Chequing</option>
          <option>Wealthsimple Chequing</option><option>RBC Chequing</option>
          <option>TD Chequing</option><option>CIBC Chequing</option>
          <option>Scotiabank</option><option>BMO Chequing</option>
          <option>National Bank</option><option>Cash</option><option>Other</option>
        </select>
      </div>
      <div class="form-group full"><label>Notes (optional)</label>
        <input type="text" id="f-notes" placeholder="e.g. March car payment to Dad">
      </div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal('add-modal')">Cancel</button>
      <button class="btn" onclick="submitAdd()">Add</button>
    </div>
  </div>
</div>

<!-- EDIT MODAL -->
<div class="modal-backdrop" id="edit-modal">
  <div class="modal">
    <div class="modal-title">Edit Transaction</div>
    <input type="hidden" id="e-id">
    <div class="form-grid">
      <div class="form-group"><label>Date</label><input type="date" id="e-date"></div>
      <div class="form-group"><label>Type</label>
        <select id="e-type" onchange="updateCatOptions('e-category','e-type')">
          <option value="Expense">Expense</option><option value="Income">Income</option>
        </select>
      </div>
      <div class="form-group full"><label>Name</label><input type="text" id="e-name"></div>
      <div class="form-group"><label>Category</label><select id="e-category"></select></div>
      <div class="form-group"><label>Amount ($)</label>
        <input type="number" id="e-amount" step="0.01" min="0">
      </div>
      <div class="form-group"><label>Account</label>
        <select id="e-account">
          <option>Tangerine Credit Card</option><option>Tangerine Chequing</option>
          <option>Wealthsimple Chequing</option><option>RBC Chequing</option>
          <option>TD Chequing</option><option>CIBC Chequing</option>
          <option>Scotiabank</option><option>BMO Chequing</option>
          <option>National Bank</option><option>Cash</option><option>Other</option>
        </select>
      </div>
      <div class="form-group full"><label>Notes</label><input type="text" id="e-notes"></div>
    </div>
    <div class="form-actions">
      <button class="btn btn-red btn-sm" onclick="deleteFromEdit()">Delete</button>
      <div style="flex:1"></div>
      <button class="btn btn-ghost" onclick="closeModal('edit-modal')">Cancel</button>
      <button class="btn" onclick="submitEdit()">Save</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const EXPENSE_CATS = ["Eating Out","Groceries","Fuel","Transport","Entertainment",
  "Subscriptions","Healthcare","Pharmacy","Clothing","Shopping","Home","Insurance",
  "Travel","Education","Phone","Internet","Utilities","Car Payment","Rent",
  "Savings Transfer","Misc","UNCATEGORIZED"];
const INCOME_CATS = ["Job","Freelance","Bonus","Refund","Other Income"];
const PALETTE = ["#6ee7b7","#f59e0b","#60a5fa","#a78bfa","#f87171","#34d399",
  "#fbbf24","#818cf8","#fb7185","#4ade80","#e879f9","#38bdf8","#fb923c","#a3e635"];

let months = [], currentMonthIdx = 0, donutChart = null;
let currentYear = new Date().getFullYear();

// ── THEME ─────────────────────────────────────────────────────────────────────
function toggleTheme() {
  const dark = document.getElementById('theme-toggle').checked;
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: dark ? 'dark' : 'light'})});
}

// ── INIT ──────────────────────────────────────────────────────────────────────
async function init() {
  // Load settings
  const settings = await fetch('/api/settings').then(r=>r.json());
  const dark = settings.theme !== 'light';
  document.getElementById('theme-toggle').checked = dark;
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');

  const res = await fetch('/api/months');
  months = await res.json();
  if (!months.length) {
    document.getElementById('month-display').textContent = 'No data yet — import a CSV!';
    return;
  }
  currentMonthIdx = 0;
  document.getElementById('f-date').value = new Date().toISOString().slice(0,10);
  populateCatFilter();
  updateCatOptions('f-category','f-type');
  populateBudgetCat();
  renderMonth();
  loadSettings();
}

const fmt = n => '$' + Math.abs(n).toLocaleString('en-CA',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtMonth = m => { const [y,mo]=m.split('-'); return new Date(y,mo-1).toLocaleString('default',{month:'long',year:'numeric'}); };

// ── MONTH NAV ─────────────────────────────────────────────────────────────────
function changeMonth(dir) {
  currentMonthIdx = Math.max(0, Math.min(months.length-1, currentMonthIdx-dir));
  renderMonth();
}

async function renderMonth() {
  const m = months[currentMonthIdx];
  document.getElementById('month-display').textContent = fmtMonth(m);
  const [summary, txns] = await Promise.all([
    fetch(`/api/summary?month=${m}`).then(r=>r.json()),
    fetch(`/api/transactions?month=${m}`).then(r=>r.json()),
  ]);
  renderCards(summary, txns);
  renderCatList(summary.by_category);
  renderDonut(summary.by_category);
  renderRecentTxns(txns.filter(t=>t.type==='Expense').slice(0,6));
  renderAverages();
  if (document.getElementById('sec-transactions').classList.contains('active')) loadTransactions();
}

// ── CARDS ─────────────────────────────────────────────────────────────────────
function renderCards(s, txns) {
  document.getElementById('card-income').textContent = fmt(s.income);
  const srcs = s.income_by_category.map(c=>`${c.category}: ${fmt(c.total)}`).join(' · ');
  document.getElementById('card-income-src').textContent = srcs || '—';

  document.getElementById('card-expense').textContent = fmt(s.expenses);
  const diff = s.expenses - s.prev_expenses;
  const vsEl = document.getElementById('card-expense-vs');
  if (s.prev_expenses > 0) {
    vsEl.textContent = (diff>=0?'↑ ':'↓ ') + fmt(Math.abs(diff)) + ' vs last month';
    vsEl.className = 'card-sub ' + (diff>0?'down':'up');
  } else { vsEl.textContent = txns.filter(t=>t.type==='Expense').length + ' transactions'; vsEl.className='card-sub'; }

  const net = document.getElementById('card-net');
  net.textContent = (s.net<0?'-':'+') + fmt(s.net);
  net.className = 'card-value ' + (s.net>=0?'green':'red');
  document.getElementById('card-net-sub').textContent = 'income − expenses';

  document.getElementById('card-rate').textContent = s.savings_rate + '%';
  const rateEl = document.getElementById('card-rate-sub');
  rateEl.textContent = s.savings_rate >= 20 ? '🎯 great saving!' : s.savings_rate >= 10 ? 'of income saved' : 'of income saved';
  rateEl.className = 'card-sub ' + (s.savings_rate>=20?'up':s.savings_rate<0?'down':'');
}

// ── CAT LIST ──────────────────────────────────────────────────────────────────
function renderCatList(cats) {
  const max = cats[0]?.total || 1;
  document.getElementById('cat-list').innerHTML = cats.length ? cats.map(c => {
    const bPct = c.budget ? Math.min(c.total/c.budget*100,100).toFixed(0) : null;
    const bColor = c.budget ? (c.total>c.budget?'var(--red)':c.total>c.budget*.8?'var(--amber)':'var(--accent)') : 'var(--accent)';
    return `<div class="cat-row" onclick="filterByCat('${c.category}')">
      <span class="cat-name">${c.category}</span>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(c.total/max*100).toFixed(0)}%;background:${bColor}"></div></div>
      ${c.budget ? `<span class="cat-budget ${c.total>c.budget?'over':''}">${Math.round(c.total/c.budget*100)}%</span>` : ''}
      <span class="cat-amt">${fmt(c.total)}</span>
    </div>`;
  }).join('') : '<div class="empty">No expenses this month</div>';
}

// ── DONUT ─────────────────────────────────────────────────────────────────────
function renderDonut(cats) {
  const ctx = document.getElementById('donut-chart').getContext('2d');
  if (donutChart) donutChart.destroy();
  if (!cats.length) return;
  donutChart = new Chart(ctx, {
    type:'doughnut',
    data:{ labels:cats.map(c=>c.category), datasets:[{data:cats.map(c=>c.total),
      backgroundColor:PALETTE, borderWidth:2, borderColor:getComputedStyle(document.documentElement).getPropertyValue('--surface').trim()}]},
    options:{cutout:'68%',plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>` ${fmt(c.raw)}`}}}}
  });
}

// ── RECURRING ─────────────────────────────────────────────────────────────────
async function renderAverages() {
  const data = await fetch('/api/averages').then(r=>r.json());
  const el = document.getElementById('averages-list');
  if (!data.length) { el.innerHTML = '<div class="empty">Not enough data yet</div>'; return; }
  const maxAvg = data[0].avg_monthly || 1;
  const n = data[0].months_seen;
  document.getElementById('avg-subtitle').textContent = `last ${n} month${n!==1?'s':''}`;
  el.innerHTML = data.map(r => `
    <div class="cat-row" onclick="filterByCat('${r.category}')" style="cursor:pointer">
      <span class="cat-name">${r.category}</span>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(r.avg_monthly/maxAvg*100).toFixed(0)}%"></div></div>
      <span class="cat-amt">${fmt(r.avg_monthly)}<span style="color:var(--muted);font-size:10px">/mo</span></span>
    </div>`).join('');
}

// ── RECENT TXNS ───────────────────────────────────────────────────────────────
function renderRecentTxns(txns) {
  document.getElementById('recent-txns').innerHTML = txns.length
    ? txns.map(t=>`<tr onclick="openEditModal(${JSON.stringify(t).replace(/"/g,'&quot;')})">
        <td style="font-family:var(--mono);color:var(--muted);font-size:11px">${t.date}</td>
        <td>${t.name}</td>
        <td><span class="badge">${t.category}</span></td>
        <td style="text-align:right" class="amt-expense">${fmt(t.amount)}</td>
      </tr>`).join('')
    : '<tr><td colspan="4" class="empty">No transactions</td></tr>';
}

// ── SEARCH & TRANSACTIONS ─────────────────────────────────────────────────────
let searchTimer = null;
function onSearchInput() { clearTimeout(searchTimer); searchTimer = setTimeout(loadTransactions, 180); }
function clearSearch() { document.getElementById('search-input').value=''; loadTransactions(); }

async function loadTransactions() {
  const m = months[currentMonthIdx] || '';
  const typ = document.getElementById('filter-type')?.value || '';
  const cat = document.getElementById('filter-cat')?.value || '';
  const search = document.getElementById('search-input')?.value.trim() || '';
  const banner = document.getElementById('search-banner');

  const url = search
    ? `/api/transactions?search=${encodeURIComponent(search)}&type=${encodeURIComponent(typ)}`
    : `/api/transactions?month=${m}&type=${encodeURIComponent(typ)}&category=${encodeURIComponent(cat)}`;

  const txns = await fetch(url).then(r=>r.json());
  const tbody = document.getElementById('all-txns');
  const empty = document.getElementById('txn-empty');

  if (search) {
    const total = txns.reduce((s,t)=>t.type==='Expense'?s+t.amount:s,0);
    banner.style.display='block';
    banner.innerHTML = `${txns.length} result${txns.length!==1?'s':''} for "<strong>${search}</strong>"` +
      (total>0?` &nbsp;·&nbsp; ${fmt(total)} total`:'') +
      ` &nbsp;<span style="cursor:pointer;color:var(--accent)" onclick="clearSearch()">✕ clear</span>`;
  } else { banner.style.display='none'; }

  if (!txns.length) { tbody.innerHTML=''; empty.style.display='block'; return; }
  empty.style.display='none';
  tbody.innerHTML = txns.map(t=>`<tr onclick="openEditModal(${JSON.stringify(t).replace(/"/g,'&quot;')})">
    <td style="font-family:var(--mono);color:var(--muted);font-size:11px">${t.date}</td>
    <td>${t.name}</td>
    <td><span class="badge">${t.category}</span></td>
    <td style="color:var(--muted);font-size:11px">${t.account}</td>
    <td><span class="badge ${t.type.toLowerCase()}">${t.type}</span></td>
    <td style="text-align:right" class="${t.type==='Income'?'amt-income':'amt-expense'}">${fmt(t.amount)}</td>
    <td><button class="del-btn" onclick="event.stopPropagation();deleteTx(${t.id})">×</button></td>
  </tr>`).join('');
}

async function deleteTx(id) {
  if (!confirm('Delete this transaction?')) return;
  await fetch(`/api/delete/${id}`, {method:'DELETE'});
  toast('Deleted','success'); renderMonth(); loadTransactions();
}
function filterByCat(cat) {
  nav('transactions');
  document.getElementById('filter-cat').value = cat;
  document.getElementById('filter-type').value = 'Expense';
  loadTransactions();
}
function populateCatFilter() {
  const sel = document.getElementById('filter-cat');
  [...EXPENSE_CATS,...INCOME_CATS].forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o);});
}

// ── YEAR VIEW ─────────────────────────────────────────────────────────────────
function changeYear(dir) { currentYear += dir; renderYear(); }
async function renderYear() {
  document.getElementById('year-display').textContent = currentYear;
  const data = await fetch(`/api/year/${currentYear}`).then(r=>r.json());
  const maxVal = Math.max(...data.months.map(m=>Math.max(m.income,m.expenses)), 1);

  document.getElementById('year-cards').innerHTML = `
    <div class="card"><div class="card-label">Total Income</div>
      <div class="card-value green">${fmt(data.total_income)}</div></div>
    <div class="card"><div class="card-label">Total Expenses</div>
      <div class="card-value red">${fmt(data.total_expenses)}</div></div>
    <div class="card"><div class="card-label">Net Saved</div>
      <div class="card-value ${data.total_income-data.total_expenses>=0?'green':'red'}">${fmt(data.total_income-data.total_expenses)}</div></div>`;

  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  document.getElementById('year-bars').innerHTML = data.months.map((m,i)=>`
    <div class="year-bar-row">
      <span class="year-month">${monthNames[i]}</span>
      <div class="year-bar-wrap">
        <div class="year-bar income" style="width:${(m.income/maxVal*100).toFixed(0)}%"></div>
        <div class="year-bar expense" style="width:${(m.expenses/maxVal*100).toFixed(0)}%"></div>
      </div>
      <div class="year-amounts">
        <span class="amt-income" style="font-size:11px">${m.income>0?fmt(m.income):''}</span>
        <span class="amt-expense" style="font-size:11px">${m.expenses>0?fmt(m.expenses):''}</span>
      </div>
    </div>`).join('');

  const maxCat = data.top_categories[0]?.total || 1;
  document.getElementById('year-cats').innerHTML = data.top_categories.length
    ? data.top_categories.map(c=>`
      <div class="cat-row">
        <span class="cat-name">${c.category}</span>
        <div class="cat-bar-wrap"><div class="cat-bar" style="width:${(c.total/maxCat*100).toFixed(0)}%"></div></div>
        <span class="cat-amt">${fmt(c.total)}</span>
      </div>`).join('')
    : '<div class="empty">No data</div>';
}

// ── SETTINGS ──────────────────────────────────────────────────────────────────
async function loadSettings() {
  loadBudgets();
  loadLearned();
}

async function loadBudgets() {
  const budgets = await fetch('/api/budgets').then(r=>r.json());
  document.getElementById('budget-list').innerHTML = budgets.length
    ? budgets.map(b=>`<div class="settings-row">
        <div><div class="settings-label">${b.category}</div>
          <div class="settings-sub">${fmt(b.monthly_limit)}/month</div></div>
        <button class="btn btn-red btn-sm" onclick="deleteBudget('${b.category}')">Remove</button>
      </div>`).join('')
    : '<div style="color:var(--muted);font-size:12px;margin-bottom:8px">No budgets set</div>';
}

function populateBudgetCat() {
  const sel = document.getElementById('budget-cat');
  EXPENSE_CATS.forEach(c=>{ const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o); });
}

async function saveBudget() {
  const cat = document.getElementById('budget-cat').value;
  const amt = document.getElementById('budget-amt').value;
  if (!cat || !amt) return toast('Select category and amount','error');
  await fetch('/api/budgets', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({category:cat, amount:parseFloat(amt)})});
  document.getElementById('budget-amt').value='';
  loadBudgets(); toast('Budget set ✓','success');
}

async function deleteBudget(cat) {
  await fetch(`/api/budgets/${encodeURIComponent(cat)}`, {method:'DELETE'});
  loadBudgets(); toast('Removed','success');
}

async function loadLearned() {
  const rows = await fetch('/api/learned').then(r=>r.json());
  document.getElementById('learned-list').innerHTML = rows.length
    ? rows.map(r=>`<div class="settings-row">
        <div><div class="settings-label" style="font-family:var(--mono);font-size:12px">${r.keyword}</div>
          <div class="settings-sub">→ ${r.category}</div></div>
        <button class="btn btn-ghost btn-sm" onclick="deleteLearned('${r.keyword.replace(/'/g,"\\'")}')">Remove</button>
      </div>`).join('')
    : '<div style="color:var(--muted);font-size:12px">None yet — edit a transaction category to start learning</div>';
}

async function deleteLearned(keyword) {
  await fetch(`/api/learned/${encodeURIComponent(keyword)}`, {method:'DELETE'});
  loadLearned(); toast('Removed','success');
}

function showBudgetPanel() {
  const el = document.getElementById('budget-panel');
  el.scrollIntoView({behavior:'smooth'});
}

// ── MODALS ────────────────────────────────────────────────────────────────────
function updateCatOptions(selId, typeId) {
  const type = document.getElementById(typeId).value;
  const sel = document.getElementById(selId);
  const cats = type === 'Income' ? INCOME_CATS : EXPENSE_CATS;
  sel.innerHTML = cats.map(c=>`<option>${c}</option>`).join('');
}

function openAddModal() {
  updateCatOptions('f-category','f-type');
  document.getElementById('add-modal').classList.add('open');
}

function openEditModal(t) {
  document.getElementById('e-id').value = t.id;
  document.getElementById('e-date').value = t.date;
  document.getElementById('e-type').value = t.type;
  document.getElementById('e-name').value = t.name;
  document.getElementById('e-amount').value = t.amount;
  document.getElementById('e-notes').value = t.notes || '';
  updateCatOptions('e-category','e-type');
  document.getElementById('e-category').value = t.category;
  const acc = document.getElementById('e-account');
  for (let o of acc.options) if (o.value===t.account) { o.selected=true; break; }
  document.getElementById('edit-modal').classList.add('open');
}

function closeModal(id) { document.getElementById(id).classList.remove('open'); }
document.querySelectorAll('.modal-backdrop').forEach(el=>
  el.addEventListener('click', e=>{ if(e.target===e.currentTarget) el.classList.remove('open'); }));

async function submitAdd() {
  const body = {
    date: document.getElementById('f-date').value,
    type: document.getElementById('f-type').value,
    name: document.getElementById('f-name').value.trim(),
    category: document.getElementById('f-category').value,
    amount: document.getElementById('f-amount').value,
    account: document.getElementById('f-account').value,
    notes: document.getElementById('f-notes').value.trim(),
  };
  if (!body.date||!body.name||!body.amount) return toast('Fill required fields','error');
  const res = await fetch('/api/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await res.json();
  if (data.ok) {
    toast('Added ✓','success'); closeModal('add-modal');
    const mr = await fetch('/api/months').then(r=>r.json()); months=mr;
    const idx = months.indexOf(body.date.slice(0,7)); if(idx!==-1) currentMonthIdx=idx;
    renderMonth();
    ['f-name','f-amount','f-notes'].forEach(id=>document.getElementById(id).value='');
  } else toast(data.error||'Error','error');
}

async function submitEdit() {
  const id = document.getElementById('e-id').value;
  const body = {
    date: document.getElementById('e-date').value,
    type: document.getElementById('e-type').value,
    name: document.getElementById('e-name').value.trim(),
    category: document.getElementById('e-category').value,
    amount: parseFloat(document.getElementById('e-amount').value),
    account: document.getElementById('e-account').value,
    notes: document.getElementById('e-notes').value.trim(),
  };
  const res = await fetch(`/api/update/${id}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await res.json();
  if (data.ok) {
    const extra = data.retro_fixed>0 ? ` · fixed ${data.retro_fixed} other${data.retro_fixed>1?'s':''}` : '';
    toast(`Saved ✓${extra}`,'success'); closeModal('edit-modal'); renderMonth(); loadTransactions();
  } else toast(data.error||'Error','error');
}

async function deleteFromEdit() {
  if (!confirm('Delete this transaction?')) return;
  await fetch(`/api/delete/${document.getElementById('e-id').value}`, {method:'DELETE'});
  toast('Deleted','success'); closeModal('edit-modal'); renderMonth(); loadTransactions();
}

// ── IMPORT ────────────────────────────────────────────────────────────────────
function handleDrop(e) {
  e.preventDefault(); document.getElementById('drop-zone').classList.remove('drag');
  handleFiles(e.dataTransfer.files);
}
async function handleFiles(files) {
  if (!files.length) return;
  const fd = new FormData();
  for (const f of files) fd.append('files', f);
  const data = await fetch('/api/import', {method:'POST', body:fd}).then(r=>r.json());
  document.getElementById('import-results').innerHTML = data.map(r=>`
    <div class="result-row">
      <div style="flex:1"><div>${r.file}</div><div class="result-bank">${r.bank}</div></div>
      <div style="color:var(--accent);font-family:var(--mono)">+${r.added}</div>
      <div style="color:var(--muted);font-size:11px">${r.dupes} dupes skipped</div>
    </div>`).join('');
  const mr = await fetch('/api/months').then(r=>r.json()); months=mr;
  if (months.length) { currentMonthIdx=0; renderMonth(); }
  toast(`Imported ${data.reduce((s,r)=>s+r.added,0)} transactions`,'success');
}

// ── NAV ───────────────────────────────────────────────────────────────────────
function nav(id) {
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById(`sec-${id}`).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b=>{
    if (b.getAttribute('onclick')?.includes(`'${id}'`)) b.classList.add('active');
  });
  if (id==='transactions') loadTransactions();
  if (id==='year') renderYear();
  if (id==='settings') loadSettings();
}

// ── EXPORT ────────────────────────────────────────────────────────────────────
function exportCSV(allTime) {
  const m = allTime ? '' : (months[currentMonthIdx]||'');
  window.location.href = `/api/export?month=${m}`;
  toast(`Downloading ${allTime?'all transactions':fmtMonth(m)} ✓`,'success');
}

// ── TOAST ─────────────────────────────────────────────────────────────────────
function toast(msg, type='success') {
  const el = document.getElementById('toast');
  el.textContent=msg; el.className=`toast ${type} show`;
  setTimeout(()=>el.classList.remove('show'), 2800);
}

init();
</script>
</body>
</html>"""

if __name__ == "__main__":
    init_db()
    print("\n🍁 CanadaFinance")
    print("   Open: http://localhost:5000")
    print("   Stop: Ctrl+C\n")
    app.run(debug=False, port=5000)
