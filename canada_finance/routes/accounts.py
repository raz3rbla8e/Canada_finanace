"""Routes for accounts, scheduled transactions, transfers, and undo."""
import json
import sqlite3
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from canada_finance.models.database import get_db, tx_hash

accounts_bp = Blueprint("accounts_extra", __name__)


# ── ACCOUNTS ──────────────────────────────────────────────────────────────────

@accounts_bp.route("/api/accounts-list")
def api_accounts_list():
    """List all registered accounts with computed balances."""
    db = get_db()
    accounts = db.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    result = []
    for a in accounts:
        income = db.execute(
            "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE account=? AND type='Income' AND hidden=0",
            (a["name"],),
        ).fetchone()["t"]
        expenses = db.execute(
            "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE account=? AND type='Expense' AND hidden=0",
            (a["name"],),
        ).fetchone()["t"]
        balance = a["opening_balance"] + income - expenses
        result.append({
            "id": a["id"],
            "name": a["name"],
            "account_type": a["account_type"],
            "opening_balance": a["opening_balance"],
            "balance": round(balance, 2),
        })
    return jsonify(result)


@accounts_bp.route("/api/accounts-list", methods=["POST"])
def api_accounts_add():
    d = request.json
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Account name is required"}), 400
    account_type = d.get("account_type", "chequing")
    if account_type not in ("chequing", "savings", "credit", "investment", "other"):
        return jsonify({"error": "Invalid account type"}), 400
    try:
        opening_balance = float(d.get("opening_balance", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid opening balance"}), 400
    db = get_db()
    try:
        db.execute(
            "INSERT INTO accounts (name, account_type, opening_balance) VALUES (?,?,?)",
            (name, account_type, opening_balance),
        )
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Account already exists"}), 409


@accounts_bp.route("/api/accounts-list/<int:aid>", methods=["PATCH"])
def api_accounts_update(aid):
    d = request.json
    db = get_db()
    acct = db.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
    if not acct:
        return jsonify({"error": "Account not found"}), 404
    name = (d.get("name") or acct["name"]).strip()
    account_type = d.get("account_type", acct["account_type"])
    try:
        opening_balance = float(d.get("opening_balance", acct["opening_balance"]))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid opening balance"}), 400
    old_name = acct["name"]
    try:
        db.execute(
            "UPDATE accounts SET name=?, account_type=?, opening_balance=? WHERE id=?",
            (name, account_type, opening_balance, aid),
        )
        if name != old_name:
            db.execute("UPDATE transactions SET account=? WHERE account=?", (name, old_name))
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Account name already exists"}), 409


@accounts_bp.route("/api/accounts-list/<int:aid>", methods=["DELETE"])
def api_accounts_delete(aid):
    db = get_db()
    db.execute("DELETE FROM accounts WHERE id=?", (aid,))
    db.commit()
    return jsonify({"ok": True})


# ── NET WORTH ─────────────────────────────────────────────────────────────────

@accounts_bp.route("/api/net-worth")
def api_net_worth():
    """Compute net worth at each month-end from accounts."""
    db = get_db()
    accounts = db.execute("SELECT * FROM accounts").fetchall()
    if not accounts:
        return jsonify([])
    months_rows = db.execute(
        "SELECT DISTINCT substr(date,1,7) as m FROM transactions WHERE hidden=0 ORDER BY m"
    ).fetchall()
    all_months = [r["m"] for r in months_rows]
    # Limit to last 24 months
    all_months = all_months[-24:]
    result = []
    for m in all_months:
        total = 0
        for a in accounts:
            like = f"{m}%"
            # Sum all transactions up to and including this month
            income = db.execute(
                "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE account=? AND type='Income' AND hidden=0 AND date <= ?",
                (a["name"], f"{m}-31"),
            ).fetchone()["t"]
            expenses = db.execute(
                "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE account=? AND type='Expense' AND hidden=0 AND date <= ?",
                (a["name"], f"{m}-31"),
            ).fetchone()["t"]
            balance = a["opening_balance"] + income - expenses
            total += balance
        result.append({"month": m, "net_worth": round(total, 2)})
    return jsonify(result)


# ── SCHEDULED TRANSACTIONS ────────────────────────────────────────────────────

@accounts_bp.route("/api/schedules")
def api_schedules_list():
    db = get_db()
    rows = db.execute("SELECT * FROM scheduled_transactions ORDER BY next_due").fetchall()
    return jsonify([dict(r) for r in rows])


@accounts_bp.route("/api/schedules", methods=["POST"])
def api_schedules_add():
    d = request.json
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    tx_type = d.get("type", "Expense")
    if tx_type not in ("Income", "Expense"):
        return jsonify({"error": "Type must be Income or Expense"}), 400
    category = (d.get("category") or "").strip()
    if not category:
        return jsonify({"error": "Category is required"}), 400
    try:
        amount = float(d.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400
    account = (d.get("account") or "").strip()
    if not account:
        return jsonify({"error": "Account is required"}), 400
    frequency = d.get("frequency", "monthly")
    if frequency not in ("weekly", "biweekly", "monthly", "yearly"):
        return jsonify({"error": "Invalid frequency"}), 400
    next_due = d.get("next_due", "")
    if not next_due:
        return jsonify({"error": "Next due date is required"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO scheduled_transactions (name, type, category, amount, account, frequency, next_due) VALUES (?,?,?,?,?,?,?)",
        (name, tx_type, category, amount, account, frequency, next_due),
    )
    db.commit()
    return jsonify({"ok": True})


@accounts_bp.route("/api/schedules/<int:sid>", methods=["PATCH"])
def api_schedules_update(sid):
    d = request.json
    db = get_db()
    sched = db.execute("SELECT * FROM scheduled_transactions WHERE id=?", (sid,)).fetchone()
    if not sched:
        return jsonify({"error": "Schedule not found"}), 404
    enabled = d.get("enabled", sched["enabled"])
    next_due = d.get("next_due", sched["next_due"])
    name = (d.get("name") or sched["name"]).strip()
    category = (d.get("category") or sched["category"]).strip()
    try:
        amount = float(d.get("amount", sched["amount"]))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
    frequency = d.get("frequency", sched["frequency"])
    db.execute(
        "UPDATE scheduled_transactions SET name=?, category=?, amount=?, frequency=?, next_due=?, enabled=? WHERE id=?",
        (name, category, amount, frequency, next_due, enabled, sid),
    )
    db.commit()
    return jsonify({"ok": True})


@accounts_bp.route("/api/schedules/<int:sid>", methods=["DELETE"])
def api_schedules_delete(sid):
    db = get_db()
    db.execute("DELETE FROM scheduled_transactions WHERE id=?", (sid,))
    db.commit()
    return jsonify({"ok": True})


@accounts_bp.route("/api/schedules/post-due", methods=["POST"])
def api_schedules_post_due():
    """Post all enabled scheduled transactions that are due today or earlier."""
    db = get_db()
    today = date.today().isoformat()
    due = db.execute(
        "SELECT * FROM scheduled_transactions WHERE enabled=1 AND next_due <= ?",
        (today,),
    ).fetchall()
    posted = 0
    for s in due:
        h = tx_hash(s["next_due"], s["name"], s["amount"], s["account"])
        existing = db.execute("SELECT id FROM transactions WHERE tx_hash=?", (h,)).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO transactions (date, type, name, category, amount, account, notes, source, tx_hash) VALUES (?,?,?,?,?,?,?,?,?)",
                (s["next_due"], s["type"], s["name"], s["category"], s["amount"],
                 s["account"], "Auto-posted from schedule", "scheduled", h),
            )
            posted += 1
        # Advance next_due
        d = date.fromisoformat(s["next_due"])
        if s["frequency"] == "weekly":
            d += timedelta(weeks=1)
        elif s["frequency"] == "biweekly":
            d += timedelta(weeks=2)
        elif s["frequency"] == "monthly":
            import calendar
            orig_day = d.day
            month = d.month + 1
            year = d.year
            if month > 12:
                month = 1
                year += 1
            max_day = calendar.monthrange(year, month)[1]
            d = date(year, month, min(orig_day, max_day))
        elif s["frequency"] == "yearly":
            import calendar
            next_year = d.year + 1
            max_day = calendar.monthrange(next_year, d.month)[1]
            d = date(next_year, d.month, min(d.day, max_day))
        db.execute("UPDATE scheduled_transactions SET next_due=? WHERE id=?", (d.isoformat(), s["id"]))
    db.commit()
    return jsonify({"ok": True, "posted": posted})


# ── TRANSFERS ─────────────────────────────────────────────────────────────────

@accounts_bp.route("/api/transfers", methods=["POST"])
def api_transfers_create():
    """Create a linked transfer between two accounts."""
    d = request.json
    from_account = (d.get("from_account") or "").strip()
    to_account = (d.get("to_account") or "").strip()
    if not from_account or not to_account:
        return jsonify({"error": "Both from_account and to_account are required"}), 400
    if from_account == to_account:
        return jsonify({"error": "Cannot transfer to same account"}), 400
    try:
        amount = float(d.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400
    tx_date = d.get("date", date.today().isoformat())
    notes = (d.get("notes") or "").strip()

    db = get_db()
    h1 = tx_hash(tx_date, f"Transfer to {to_account}", amount, from_account)
    h2 = tx_hash(tx_date, f"Transfer from {from_account}", amount, to_account)

    # Outflow from source
    db.execute(
        "INSERT INTO transactions (date, type, name, category, amount, account, notes, source, tx_hash, hidden) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (tx_date, "Expense", f"Transfer to {to_account}", "Transfer", amount,
         from_account, notes, "transfer", h1, 1),
    )
    out_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Inflow to destination
    db.execute(
        "INSERT INTO transactions (date, type, name, category, amount, account, notes, source, tx_hash, hidden, transfer_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (tx_date, "Income", f"Transfer from {from_account}", "Transfer", amount,
         to_account, notes, "transfer", h2, 1, out_id),
    )
    in_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Link outflow to inflow
    db.execute("UPDATE transactions SET transfer_id=? WHERE id=?", (in_id, out_id))
    db.commit()
    return jsonify({"ok": True, "from_id": out_id, "to_id": in_id})


# ── UNDO ──────────────────────────────────────────────────────────────────────

def save_undo(db, action, data):
    """Save an undo record. Keep only last 50 entries."""
    db.execute(
        "INSERT INTO undo_history (action, data) VALUES (?,?)",
        (action, json.dumps(data)),
    )
    db.execute("""
        DELETE FROM undo_history WHERE id NOT IN (
            SELECT id FROM undo_history ORDER BY id DESC LIMIT 50
        )
    """)


@accounts_bp.route("/api/undo", methods=["POST"])
def api_undo():
    """Undo the last action."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM undo_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return jsonify({"error": "Nothing to undo"}), 404
    action = row["action"]
    data = json.loads(row["data"])

    if action == "delete":
        # Restore deleted transaction
        t = data
        db.execute(
            "INSERT INTO transactions (date, type, name, category, amount, account, notes, source, tx_hash, hidden) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (t["date"], t["type"], t["name"], t["category"], t["amount"],
             t["account"], t.get("notes", ""), t.get("source", "manual"),
             t.get("tx_hash"), t.get("hidden", 0)),
        )
    elif action == "update":
        # Restore previous version
        old = data["old"]
        tid = data["id"]
        db.execute(
            "UPDATE transactions SET date=?, type=?, name=?, category=?, amount=?, account=?, notes=? WHERE id=?",
            (old["date"], old["type"], old["name"], old["category"],
             old["amount"], old["account"], old.get("notes", ""), tid),
        )
    elif action == "bulk_delete":
        for t in data:
            db.execute(
                "INSERT INTO transactions (date, type, name, category, amount, account, notes, source, tx_hash, hidden) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (t["date"], t["type"], t["name"], t["category"], t["amount"],
                 t["account"], t.get("notes", ""), t.get("source", "manual"),
                 t.get("tx_hash"), t.get("hidden", 0)),
            )

    db.execute("DELETE FROM undo_history WHERE id=?", (row["id"],))
    db.commit()
    return jsonify({"ok": True, "action": action})


@accounts_bp.route("/api/undo/status")
def api_undo_status():
    """Check if there's something to undo."""
    db = get_db()
    row = db.execute(
        "SELECT action, created_at FROM undo_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row:
        return jsonify({"available": True, "action": row["action"], "when": row["created_at"]})
    return jsonify({"available": False})
