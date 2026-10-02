from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from database.queries import get_user_by_id, get_summary_stats, get_recent_transactions, get_category_breakdown
from werkzeug.security import check_password_hash
import sqlite3
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = "dev-secret-key-for-spendly"

with app.app_context():
    init_db()
    seed_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this page.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def guest_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" in session:
            return redirect(url_for("landing"))
        return f(*args, **kwargs)
    return decorated_function


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
@guest_only
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Validation
        if not all([name, email, password, confirm_password]):
            flash("All fields are required.")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("register.html")

        try:
            create_user(name, email, password)
            flash("Account created successfully! Please sign in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.")
            return render_template("register.html")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@guest_only
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("All fields are required.")
            return render_template("login.html")

        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("profile"))


        flash("Invalid email or password.")
        return render_template("login.html")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/profile")
@login_required
def profile():
    uid = session["user_id"]
    user_info = get_user_by_id(uid)

    if not user_info:
        abort(404)

    # Calculate initials (First letter of first and last name)
    name_parts = user_info["name"].split()
    initials = "".join([p[0].upper() for p in name_parts if p])
    user_info["initials"] = initials if initials else "?"

    # Calculate summary statistics
    stats_data = get_summary_stats(uid)
    summary_stats = [
        {"label": "Total Spent", "value": f"₹{stats_data['total_spent']:,.2f}", "trend": "—"},
        {"label": "Transactions", "value": str(stats_data['transaction_count']), "trend": "—"},
        {"label": "Top Category", "value": stats_data['top_category'], "trend": "—"}
    ]

    # Get recent transactions from DB
    raw_transactions = get_recent_transactions(uid)
    transactions = []
    for tx in raw_transactions:
        # Format date: '2026-10-01' -> 'Oct 1, 2026'
        dt = datetime.strptime(tx["date"], "%Y-%m-%d")
        formatted_date = dt.strftime("%b %-d, %Y")

        # Format amount: 450.0 -> '-₹450.00' (with thousands separator)
        formatted_amount = f"-₹{tx['amount']:,.2f}"

        transactions.append({
            "date": formatted_date,
            "description": tx["description"],
            "category": tx["category"],
            "amount": formatted_amount
        })

    # Get category breakdown from DB
    raw_categories = get_category_breakdown(uid)
    categories = []
    for cat in raw_categories:
        categories.append({
            "name": cat["name"],
            "amount": f"₹{cat['amount']:,.2f}",
            "percentage": cat["pct"]
        })

    return render_template(
        "profile.html",
        user=user_info,
        stats=summary_stats,
        transactions=transactions,
        categories=categories
    )



@app.route("/expenses/add")
@login_required
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
@login_required
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
@login_required
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
