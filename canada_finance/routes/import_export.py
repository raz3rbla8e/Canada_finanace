import csv
import io
import os
import re
from datetime import datetime

import yaml
from flask import Blueprint, jsonify, request, Response

from canada_finance.config import BANKS_DIR
from canada_finance.models.database import get_db
from canada_finance.services.categorization import load_learned_dict
from canada_finance.services.csv_parser import (
    load_bank_configs, detect_bank_config, parse_with_config,
)
from canada_finance.services.rules_engine import save_transactions

import_export_bp = Blueprint("import_export", __name__)


@import_export_bp.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large — max 16 MB"}), 413


@import_export_bp.route("/api/import", methods=["POST"])
def api_import():
    db = get_db()
    learned = load_learned_dict(db)
    configs = load_bank_configs()
    results = []
    for f in request.files.getlist("files"):
        raw = f.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = raw.decode("latin-1")
            except UnicodeDecodeError:
                results.append({
                    "file": f.filename, "bank": "unknown", "added": 0, "dupes": 0,
                    "last_verified": "", "error": "Unsupported file encoding",
                })
                continue
        first_line = text.splitlines()[0] if text.strip() else ""
        config, bank_name = detect_bank_config(first_line, configs)
        if config:
            txns = parse_with_config(text, config, learned)
            added, dupes = save_transactions(txns)
            results.append({
                "file": f.filename, "bank": config.get("name", bank_name),
                "added": added, "dupes": dupes,
                "last_verified": config.get("last_verified", ""),
            })
        else:
            results.append({
                "file": f.filename, "bank": "unknown", "added": 0, "dupes": 0,
                "last_verified": "",
            })
    return jsonify(results)


@import_export_bp.route("/api/detect-csv", methods=["POST"])
def api_detect_csv():
    """Detect bank from CSV; if unknown, return headers + preview rows."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file provided"}), 400
    text = f.read().decode("utf-8-sig")
    lines = text.splitlines()
    if not lines:
        return jsonify({"error": "Empty file"}), 400
    configs = load_bank_configs()
    config, bank_name = detect_bank_config(lines[0], configs)
    if config:
        return jsonify({"detected": True, "bank": config.get("name", bank_name),
                        "config_name": bank_name})
    # Unknown — return headers + preview rows
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    preview = []
    for i, row in enumerate(reader):
        if i >= 5:
            break
        preview.append(dict(row))
    return jsonify({"detected": False, "headers": headers, "preview": preview,
                    "raw_text": text})


@import_export_bp.route("/api/save-bank-config", methods=["POST"])
def api_save_bank_config():
    """Save a user-defined bank config from the unknown CSV wizard."""
    d = request.json
    bank_name = d.get("bank_name", "").strip()
    if not bank_name:
        return jsonify({"error": "Bank name is required"}), 400
    date_col = d.get("date_column", "")
    desc_col = d.get("description_column", "")
    amount_mode = d.get("amount_mode", "single")
    date_format = d.get("date_format", "%Y-%m-%d")
    if not date_col or not desc_col:
        return jsonify({"error": "Date and description columns are required"}), 400
    # Build config
    slug = re.sub(r"[^a-z0-9]+", "_", bank_name.lower()).strip("_")
    config = {
        "name": bank_name,
        "version": 1,
        "last_verified": datetime.now().strftime("%Y-%m"),
        "account_label": bank_name,
        "encoding": "utf-8-sig",
        "detection": {"header_contains": d.get("detection_headers", [])},
        "columns": {"date": date_col, "description": desc_col},
        "date_formats": [date_format],
    }
    if amount_mode == "single":
        config["columns"]["amount"] = d.get("amount_column", "")
        config["amount_sign"] = d.get("amount_sign", "standard")
    else:
        config["columns"]["debit"] = d.get("debit_column", "")
        config["columns"]["credit"] = d.get("credit_column", "")
    # Save YAML
    fname = f"{slug}.yaml"
    fpath = os.path.join(BANKS_DIR, fname)
    os.makedirs(BANKS_DIR, exist_ok=True)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(f"# {bank_name} (user-created)\n")
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return jsonify({"ok": True, "config_file": fname, "config_name": slug})


@import_export_bp.route("/api/preview-parse", methods=["POST"])
def api_preview_parse():
    """Preview parsing with a user-defined config (before saving)."""
    d = request.json
    text = d.get("raw_text", "")
    mapping = d.get("mapping", {})
    if not text or not mapping:
        return jsonify({"error": "Missing data"}), 400
    # Build a temporary config from the mapping
    config = {
        "columns": {
            "date": mapping.get("date_column", ""),
            "description": mapping.get("description_column", ""),
        },
        "date_formats": [mapping.get("date_format", "%Y-%m-%d")],
        "account_label": mapping.get("bank_name", "Unknown Bank"),
    }
    if mapping.get("amount_mode") == "single":
        config["columns"]["amount"] = mapping.get("amount_column", "")
        config["amount_sign"] = mapping.get("amount_sign", "standard")
    else:
        config["columns"]["debit"] = mapping.get("debit_column", "")
        config["columns"]["credit"] = mapping.get("credit_column", "")
    txns = parse_with_config(text, config, {})
    return jsonify({"transactions": txns[:10], "total": len(txns)})


@import_export_bp.route("/api/export")
def api_export():
    month = request.args.get("month", "")
    include_hidden = request.args.get("include_hidden", "0") == "1"
    db = get_db()
    q = "SELECT date,type,name,category,amount,account,notes,source FROM transactions"
    conditions = []
    params = []
    if not include_hidden:
        conditions.append("hidden=0")
    if month:
        conditions.append("date LIKE ?")
        params.append(f"{month}%")
    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    q += " ORDER BY date DESC"
    rows = db.execute(q, params).fetchall()

    def generate():
        yield "Date,Type,Name,Category,Amount,Account,Notes,Source\n"
        for r in rows:
            yield ",".join(
                '"' + str(v if v is not None else '').replace('"', '""') + '"'
                for v in r
            ) + "\n"

    filename = f"transactions_{month or 'all'}.csv"
    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@import_export_bp.route("/api/backup")
def api_backup():
    """Download the full SQLite database file as a backup."""
    from canada_finance.config import DB_PATH
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "No database found"}), 404
    with open(DB_PATH, "rb") as f:
        data = f.read()
    filename = f"finance_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return Response(data, mimetype="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@import_export_bp.route("/api/restore", methods=["POST"])
def api_restore():
    """Restore the database from an uploaded .db file."""
    from canada_finance.config import DB_PATH
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file provided"}), 400
    if not f.filename.endswith(".db"):
        return jsonify({"error": "File must be a .db file"}), 400
    header = f.read(16)
    if header[:16] != b"SQLite format 3\x00":
        return jsonify({"error": "Not a valid SQLite database"}), 400
    f.seek(0)
    # Close the current connection before overwriting
    db = get_db()
    db.close()
    with open(DB_PATH, "wb") as out:
        out.write(f.read())
    return jsonify({"ok": True, "message": "Database restored successfully"})


@import_export_bp.route("/api/export/pdf")
def api_export_pdf():
    """Export a PDF report for a given month."""
    from fpdf import FPDF

    month = request.args.get("month", "")
    include_transactions = request.args.get("include_transactions", "0") == "1"
    if not month:
        return jsonify({"error": "Month parameter required (YYYY-MM)"}), 400

    db = get_db()
    like = f"{month}%"
    income = db.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Income' AND hidden=0 AND date LIKE ?",
        (like,),
    ).fetchone()["t"]
    expenses = db.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE type='Expense' AND hidden=0 AND date LIKE ?",
        (like,),
    ).fetchone()["t"]
    by_cat = db.execute(
        """SELECT category, SUM(amount) as total FROM transactions
           WHERE type='Expense' AND hidden=0 AND date LIKE ? GROUP BY category ORDER BY total DESC""",
        (like,),
    ).fetchall()
    budgets = {
        r["category"]: r["monthly_limit"]
        for r in db.execute("SELECT category, monthly_limit FROM budgets").fetchall()
    }

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, f"Finance Report - {month}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Summary box
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    net = income - expenses
    savings_rate = round((net / income * 100), 1) if income > 0 else 0
    pdf.cell(0, 7, f"Income:  ${income:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Expenses:  ${expenses:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Net:  ${net:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Savings Rate:  {savings_rate}%", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Spending by category table
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Spending by Category", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 7, "Category", border=1)
    pdf.cell(40, 7, "Spent", border=1, align="R")
    pdf.cell(40, 7, "Budget", border=1, align="R")
    pdf.ln()
    pdf.set_font("Helvetica", "", 10)
    for r in by_cat:
        cat = r["category"]
        pdf.cell(80, 7, cat[:30], border=1)
        pdf.cell(40, 7, f"${r['total']:,.2f}", border=1, align="R")
        budget_val = budgets.get(cat)
        pdf.cell(40, 7, f"${budget_val:,.2f}" if budget_val else "-", border=1, align="R")
        pdf.ln()
    pdf.ln(4)

    # Optional transaction listing
    if include_transactions:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Transactions", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(22, 6, "Date", border=1)
        pdf.cell(60, 6, "Name", border=1)
        pdf.cell(35, 6, "Category", border=1)
        pdf.cell(25, 6, "Amount", border=1, align="R")
        pdf.cell(20, 6, "Type", border=1)
        pdf.ln()
        pdf.set_font("Helvetica", "", 8)
        rows = db.execute(
            "SELECT date, name, category, amount, type FROM transactions WHERE hidden=0 AND date LIKE ? ORDER BY date DESC",
            (like,),
        ).fetchall()
        for r in rows:
            pdf.cell(22, 6, r["date"], border=1)
            pdf.cell(60, 6, str(r["name"])[:28], border=1)
            pdf.cell(35, 6, str(r["category"])[:16], border=1)
            pdf.cell(25, 6, f"${r['amount']:,.2f}", border=1, align="R")
            pdf.cell(20, 6, r["type"], border=1)
            pdf.ln()

    pdf_bytes = bytes(pdf.output())
    filename = f"finance_report_{month}.pdf"
    return Response(pdf_bytes, mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})