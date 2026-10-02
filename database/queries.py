from database.db import get_db
from datetime import datetime

def get_user_by_id(user_id):
    """
    Fetches a user record by ID and formats the member_since date.
    Returns: {'name': str, 'email': str, 'member_since': str} or None
    """
    with get_db() as conn:
        user = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if user:
            # Handle various SQLite date formats (ISO 8601 with 'T' or space)
            date_str = user['created_at'].replace('T', ' ')
            # Strip microseconds if present to match '%Y-%m-%d %H:%M:%S'
            if '.' in date_str:
                date_str = date_str.split('.')[0]

            dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            member_since = dt.strftime('%B %Y')
            return {
                "name": user['name'],
                "email": user['email'],
                "member_since": member_since
            }
        return None

def get_recent_transactions(user_id, limit=10):
    """
    Fetches the most recent transactions for a user.
    Returns: A list of dicts: {'date': str, 'description': str, 'category': str, 'amount': float}
    """
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT date, description, category, amount FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit)
        )
        return [
            {
                "date": row["date"],
                "description": row["description"],
                "category": row["category"],
                "amount": row["amount"]
            }
            for row in cursor
        ]

def get_category_breakdown(user_id):
    """
    Calculates total spending per category for a user.
    Returns: A list of dicts: {'name': str, 'amount': float, 'pct': int}
    Sorted by amount DESC. Sum of pct is guaranteed to be 100.
    """
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,)
        )
        rows = cursor.fetchall()


        if not rows:
            return []

        total_spent = sum(row["total"] for row in rows)
        if total_spent == 0:
            return [{"name": row["category"], "amount": row["total"], "pct": 0} for row in rows]

        breakdown = []
        sum_pct = 0
        for i, row in enumerate(rows):
            pct = int((row["total"] / total_spent) * 100)
            # For the last item, adjust pct to ensure total is 100
            if i == len(rows) - 1:
                pct = 100 - sum_pct

            breakdown.append({
                "name": row["category"],
                "amount": row["total"],
                "pct": pct
            })
            sum_pct += pct

        return breakdown

def get_summary_stats(user_id):
    """
    Calculates summary statistics for a user's expenses.
    Returns: {'total_spent': float, 'transaction_count': int, 'top_category': str}
    """
    with get_db() as conn:
        # Total spent and transaction count
        # Using 'expenses' table as it's consistent with other queries in this file
        stats = conn.execute(
            "SELECT SUM(amount), COUNT(*) FROM expenses WHERE user_id = ?",
            (user_id,)
        ).fetchone()


        total_spent = stats[0] if stats[0] is not None else 0.0
        transaction_count = stats[1] if stats[1] is not None else 0

        # Top category by total spend
        category_row = conn.execute(
            """
            SELECT category FROM expenses
            WHERE user_id = ?
            GROUP BY category
            ORDER BY SUM(amount) DESC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()

        top_category = category_row['category'] if category_row else "None"

        return {
            'total_spent': float(total_spent),
            'transaction_count': transaction_count,
            'top_category': top_category
        }
