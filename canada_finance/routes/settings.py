import sqlite3

from flask import Blueprint, jsonify, request

from canada_finance.models.database import get_db

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/budgets", methods=["GET"])
def api_budgets_get():
    db = get_db()
    rows = db.execute("SELECT category, monthly_limit FROM budgets").fetchall()
    return jsonify([dict(r) for r in rows])


@settings_bp.route("/api/budgets", methods=["POST"])
def api_budgets_set():
    d = request.json
    if not d or "category" not in d or "amount" not in d:
        return jsonify({"error": "Category and amount required"}), 400
    try:
        amount = float(d["amount"])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
    db = get_db()
    db.execute("""INSERT INTO budgets (category, monthly_limit) VALUES (?,?)
        ON CONFLICT(category) DO UPDATE SET monthly_limit=excluded.monthly_limit
    """, (d["category"], amount))
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/budgets/<string:cat>", methods=["DELETE"])
def api_budgets_del(cat):
    db = get_db()
    db.execute("DELETE FROM budgets WHERE category=?", (cat,))
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/learned")
def api_learned():
    db = get_db()
    rows = db.execute(
        "SELECT keyword, category, updated_at FROM learned_merchants ORDER BY updated_at DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@settings_bp.route("/api/learned/<path:keyword>", methods=["DELETE"])
def api_learned_del(keyword):
    db = get_db()
    db.execute("DELETE FROM learned_merchants WHERE keyword=?", (keyword,))
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/settings", methods=["GET"])
def api_settings_get():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return jsonify({r["key"]: r["value"] for r in rows})


@settings_bp.route("/api/settings", methods=["POST"])
def api_settings_set():
    d = request.json
    if not d:
        return jsonify({"error": "Request body required"}), 400
    db = get_db()
    for key, val in d.items():
        db.execute(
            "INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, val),
        )
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/categories")
def api_categories_get():
    db = get_db()
    rows = db.execute(
        "SELECT id, name, type, icon, user_created, sort_order, group_id FROM categories ORDER BY type, sort_order"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@settings_bp.route("/api/categories", methods=["POST"])
def api_categories_add():
    d = request.json
    name = d.get("name", "").strip()
    cat_type = d.get("type", "Expense")
    icon = d.get("icon", "").strip()
    if not name:
        return jsonify({"error": "Category name is required"}), 400
    if cat_type not in ("Income", "Expense"):
        return jsonify({"error": "Type must be Income or Expense"}), 400
    db = get_db()
    max_order = db.execute(
        "SELECT COALESCE(MAX(sort_order),0) FROM categories WHERE type=?", (cat_type,)
    ).fetchone()[0]
    try:
        db.execute(
            "INSERT INTO categories (name, type, icon, user_created, sort_order) VALUES (?,?,?,1,?)",
            (name, cat_type, icon, max_order + 1),
        )
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Category already exists"}), 409


@settings_bp.route("/api/categories/<int:cat_id>", methods=["PATCH"])
def api_categories_update(cat_id):
    d = request.json
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    if not cat:
        return jsonify({"error": "Category not found"}), 404
    old_name = cat["name"]
    new_name = d.get("name", old_name).strip()
    new_icon = d.get("icon", cat["icon"]).strip()
    new_group_id = d.get("group_id", cat["group_id"])
    if not new_name:
        return jsonify({"error": "Category name is required"}), 400
    try:
        db.execute("UPDATE categories SET name=?, icon=?, group_id=? WHERE id=?", (new_name, new_icon, new_group_id, cat_id))
        if new_name != old_name:
            db.execute("UPDATE transactions SET category=? WHERE category=?", (new_name, old_name))
            db.execute("UPDATE learned_merchants SET category=? WHERE category=?", (new_name, old_name))
            db.execute("UPDATE budgets SET category=? WHERE category=?", (new_name, old_name))
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "A category with that name already exists"}), 409


@settings_bp.route("/api/categories/<int:cat_id>", methods=["DELETE"])
def api_categories_delete(cat_id):
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    if not cat:
        return jsonify({"error": "Category not found"}), 404
    reassign_to = request.args.get("reassign", "")
    usage = db.execute(
        "SELECT COUNT(*) as c FROM transactions WHERE category=?", (cat["name"],)
    ).fetchone()["c"]
    if usage > 0 and not reassign_to:
        return jsonify({
            "error": "in_use",
            "count": usage,
            "message": f"{usage} transactions use this category. Provide a reassign target.",
        }), 409
    if usage > 0 and reassign_to:
        db.execute("UPDATE transactions SET category=? WHERE category=?", (reassign_to, cat["name"]))
        db.execute("UPDATE budgets SET category=? WHERE category=?", (reassign_to, cat["name"]))
        db.execute("UPDATE learned_merchants SET category=? WHERE category=?", (reassign_to, cat["name"]))
    db.execute("DELETE FROM budgets WHERE category=?", (cat["name"],))
    db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    db.commit()
    return jsonify({"ok": True, "reassigned": usage if reassign_to else 0})


# ── SAVINGS GOALS ─────────────────────────────────────────────────────────────

@settings_bp.route("/api/goals")
def api_goals_get():
    db = get_db()
    rows = db.execute("SELECT * FROM savings_goals ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@settings_bp.route("/api/goals", methods=["POST"])
def api_goals_add():
    d = request.json
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Goal name is required"}), 400
    try:
        target = float(d.get("target_amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid target amount"}), 400
    if target <= 0:
        return jsonify({"error": "Target must be positive"}), 400
    icon = (d.get("icon") or "🎯").strip()
    db = get_db()
    db.execute(
        "INSERT INTO savings_goals (name, target_amount, icon) VALUES (?,?,?)",
        (name, target, icon),
    )
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/goals/<int:gid>", methods=["PATCH"])
def api_goals_update(gid):
    d = request.json
    db = get_db()
    goal = db.execute("SELECT * FROM savings_goals WHERE id=?", (gid,)).fetchone()
    if not goal:
        return jsonify({"error": "Goal not found"}), 404
    name = (d.get("name") or goal["name"]).strip()
    target = d.get("target_amount", goal["target_amount"])
    current = d.get("current_amount", goal["current_amount"])
    icon = (d.get("icon") or goal["icon"]).strip()
    try:
        target = float(target)
        current = float(current)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
    db.execute(
        "UPDATE savings_goals SET name=?, target_amount=?, current_amount=?, icon=? WHERE id=?",
        (name, target, current, icon, gid),
    )
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/goals/<int:gid>", methods=["DELETE"])
def api_goals_delete(gid):
    db = get_db()
    db.execute("DELETE FROM savings_goals WHERE id=?", (gid,))
    db.commit()
    return jsonify({"ok": True})


@settings_bp.route("/api/goals/<int:gid>/contribute", methods=["POST"])
def api_goals_contribute(gid):
    d = request.json
    try:
        amount = float(d.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400
    db = get_db()
    goal = db.execute("SELECT * FROM savings_goals WHERE id=?", (gid,)).fetchone()
    if not goal:
        return jsonify({"error": "Goal not found"}), 404
    new_amount = goal["current_amount"] + amount
    db.execute("UPDATE savings_goals SET current_amount=? WHERE id=?", (new_amount, gid))
    db.commit()
    return jsonify({"ok": True, "current_amount": new_amount})


# ── CATEGORY GROUPS ───────────────────────────────────────────────────────────

@settings_bp.route("/api/category-groups")
def api_category_groups_get():
    db = get_db()
    groups = db.execute("SELECT * FROM category_groups ORDER BY sort_order").fetchall()
    result = []
    for g in groups:
        cats = db.execute(
            "SELECT id, name FROM categories WHERE group_id=? ORDER BY sort_order",
            (g["id"],),
        ).fetchall()
        result.append({
            "id": g["id"], "name": g["name"], "sort_order": g["sort_order"],
            "categories": [dict(c) for c in cats],
        })
    # Ungrouped expense categories
    ungrouped = db.execute(
        "SELECT id, name FROM categories WHERE group_id IS NULL AND type='Expense' ORDER BY sort_order"
    ).fetchall()
    if ungrouped:
        result.append({
            "id": None, "name": "Other", "sort_order": 999,
            "categories": [dict(c) for c in ungrouped],
        })
    return jsonify(result)


@settings_bp.route("/api/category-groups", methods=["POST"])
def api_category_groups_add():
    d = request.json
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Group name is required"}), 400
    db = get_db()
    max_order = db.execute("SELECT COALESCE(MAX(sort_order),0) FROM category_groups").fetchone()[0]
    try:
        db.execute(
            "INSERT INTO category_groups (name, sort_order) VALUES (?,?)",
            (name, max_order + 1),
        )
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Group already exists"}), 409


@settings_bp.route("/api/category-groups/<int:gid>", methods=["PATCH"])
def api_category_groups_update(gid):
    d = request.json
    db = get_db()
    group = db.execute("SELECT * FROM category_groups WHERE id=?", (gid,)).fetchone()
    if not group:
        return jsonify({"error": "Group not found"}), 404
    name = (d.get("name") or group["name"]).strip()
    try:
        db.execute("UPDATE category_groups SET name=? WHERE id=?", (name, gid))
        db.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Group name already exists"}), 409


@settings_bp.route("/api/category-groups/<int:gid>", methods=["DELETE"])
def api_category_groups_delete(gid):
    db = get_db()
    db.execute("UPDATE categories SET group_id=NULL WHERE group_id=?", (gid,))
    db.execute("DELETE FROM category_groups WHERE id=?", (gid,))
    db.commit()
    return jsonify({"ok": True})
