import glob
import os
import sqlite3

from flask import Blueprint, render_template, jsonify, current_app

from canada_finance.config import DB_PATH, SAMPLE_DATA_DIR, BANKS_DIR

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/icon-compare")
def icon_compare():
    return render_template("icon_compare.html")


@main_bp.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "db_exists": os.path.isfile(DB_PATH),
    })


@main_bp.route("/api/demo")
def api_demo():
    return jsonify({"demo": current_app.config.get("DEMO_MODE", False)})


@main_bp.route("/api/demo/reset", methods=["POST"])
def api_demo_reset():
    if not current_app.config.get("DEMO_MODE"):
        return jsonify({"error": "Not in demo mode"}), 403
    _seed_demo_data()
    return jsonify({"ok": True, "message": "Demo data reset"})


def _seed_demo_data(wipe=True):
    """Seed (or re-seed) the database with comprehensive demo data."""
    from datetime import date, timedelta
    from canada_finance.models.database import get_db
    from canada_finance.services.categorization import load_learned_dict
    from canada_finance.services.csv_parser import load_bank_configs, detect_bank_config, parse_with_config
    from canada_finance.services.rules_engine import save_transactions

    db = get_db()
    if wipe:
        for table in ("transactions", "accounts", "savings_goals",
                       "scheduled_transactions", "budgets", "learned_merchants",
                       "import_rules", "rule_conditions", "undo_history"):
            db.execute(f"DELETE FROM {table}")
        db.commit()

    # ── 1. Import sample CSV transactions ──────────────────────────────────────
    learned = load_learned_dict(db)
    configs = load_bank_configs()
    total_added = 0

    csv_files = sorted(glob.glob(os.path.join(SAMPLE_DATA_DIR, "*.csv")))
    for csv_path in csv_files:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            text = f.read()
        first_line = text.splitlines()[0] if text.strip() else ""
        config, bank_name = detect_bank_config(first_line, configs)
        if config:
            txns = parse_with_config(text, config, learned)
            added, dupes = save_transactions(txns)
            total_added += added

    # ── 2. Accounts (3 types) ──────────────────────────────────────────────────
    demo_accounts = [
        ("RBC Chequing", "chequing", 5000),
        ("TD Savings", "savings", 12000),
        ("Tangerine Credit Card", "credit", 0),
    ]
    for name, acct_type, balance in demo_accounts:
        try:
            db.execute(
                "INSERT INTO accounts (name, account_type, opening_balance) VALUES (?,?,?)",
                (name, acct_type, balance),
            )
        except sqlite3.IntegrityError:
            pass

    # ── 3. Savings goals (with progress) ───────────────────────────────────────
    demo_goals = [
        ("Vacation Fund", 3000, 1250, "✈️"),
        ("Emergency Fund", 10000, 4200, "🛡️"),
        ("New Laptop", 2000, 800, "💻"),
    ]
    for name, target, current, icon in demo_goals:
        try:
            db.execute(
                "INSERT INTO savings_goals (name, target_amount, current_amount, icon) VALUES (?,?,?,?)",
                (name, target, current, icon),
            )
        except sqlite3.IntegrityError:
            pass

    # ── 4. Scheduled transactions (multiple frequencies + accounts) ────────────
    today = date.today()
    next_month = today.replace(day=1) + timedelta(days=32)
    next_month = next_month.replace(day=1)
    demo_schedules = [
        ("Netflix", "Expense", "Subscriptions", 17.99, "RBC Chequing", "monthly", next_month.isoformat()),
        ("Spotify", "Expense", "Subscriptions", 11.99, "RBC Chequing", "monthly", next_month.isoformat()),
        ("Rent", "Expense", "Rent", 1800.00, "RBC Chequing", "monthly", next_month.isoformat()),
        ("Paycheque", "Income", "Job", 3200.00, "RBC Chequing", "biweekly", (today + timedelta(days=7)).isoformat()),
        ("Gym Membership", "Expense", "Healthcare", 49.99, "TD Savings", "monthly", next_month.isoformat()),
    ]
    for name, tx_type, cat, amount, acct, freq, due in demo_schedules:
        db.execute(
            "INSERT INTO scheduled_transactions (name, type, category, amount, account, frequency, next_due) VALUES (?,?,?,?,?,?,?)",
            (name, tx_type, cat, amount, acct, freq, due),
        )

    # ── 5. Budgets ─────────────────────────────────────────────────────────────
    demo_budgets = [
        ("Eating Out", 150),
        ("Groceries", 400),
        ("Entertainment", 100),
        ("Subscriptions", 60),
        ("Fuel", 120),
        ("Clothing", 80),
    ]
    for cat, limit_val in demo_budgets:
        db.execute(
            "INSERT OR REPLACE INTO budgets (category, monthly_limit) VALUES (?,?)",
            (cat, limit_val),
        )

    # ── 6. Import rules (auto-hide + categorize) ──────────────────────────────
    # Rule 1: Auto-hide credit card payments (inter-account transfers)
    db.execute(
        "INSERT INTO import_rules (name, action, enabled, priority) VALUES (?,?,1,1)",
        ("Auto-hide: CC Payment transfers", "hide"),
    )
    rule_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO rule_conditions (rule_id, field, operator, value) VALUES (?,?,?,?)",
        (rule_id, "description", "contains", "INTERAC e-Transfer TO VISA"),
    )
    # Rule 2: Label large purchases
    db.execute(
        "INSERT INTO import_rules (name, action, enabled, priority) VALUES (?,?,1,2)",
        ("Label: Large purchases over $500", "label"),
    )
    rule_id2 = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO rule_conditions (rule_id, field, operator, value) VALUES (?,?,?,?)",
        (rule_id2, "amount", "greater_than", "500"),
    )

    # ── 7. Learned merchants ──────────────────────────────────────────────────
    demo_learned = [
        ("TIM HORTONS", "Eating Out"),
        ("COSTCO WHOLESALE", "Groceries"),
        ("SHELL", "Fuel"),
        ("AMAZON.CA", "Shopping"),
        ("CANADIAN TIRE", "Home"),
    ]
    for keyword, cat in demo_learned:
        db.execute(
            "INSERT OR REPLACE INTO learned_merchants (keyword, category) VALUES (?,?)",
            (keyword, cat),
        )

    db.commit()
    return total_added
