import pytest
from app import app as flask_app
from database.db import init_db, create_user
from database.queries import get_expense_by_id, update_expense
import sqlite3


@pytest.fixture
def app():
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE": ":memory:",  # isolated in-memory DB per test
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
        }
    )

    # Monkeypatch get_db to use the in-memory database for this app instance
    import database.db

    original_get_db = database.db.get_db

    def test_get_db():
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # Note: Since we are using :memory:, we need a persistent connection
    # for the duration of the test to avoid losing the schema.
    # However, the application pattern uses get_db() which opens a new connection.
    # For :memory: to work across calls, we'd usually need a shared connection.
    # Instead, we will use a temporary file for the test database to ensure consistency.
    import os
    import tempfile

    db_fd, db_path = tempfile.mkstemp()
    database.db.DB_PATH = db_path

    with flask_app.app_context():
        init_db()
        yield flask_app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """A test client that is already logged in."""
    # We use the create_user helper or register route
    client.post(
        "/register",
        data={
            "name": "Test User",
            "email": "test@test.com",
            "password": "testpass",
            "confirm_password": "testpass",
        },
    )
    client.post("/login", data={"email": "test@test.com", "password": "testpass"})
    return client


# ------------------------------------------------------------------ #
# Unit Tests for database/queries.py
# ------------------------------------------------------------------ #


class TestExpenseQueries:
    def test_get_expense_by_id_valid(self, app):
        from database.db import get_db

        # Setup
        uid = create_user("User", "u@u.com", "pass")
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (uid, 100.0, "Food", "2023-01-01", "Dinner"),
            )
            eid = cursor.lastrowid

        # Test
        expense = get_expense_by_id(eid, uid)
        assert expense is not None
        assert expense["amount"] == 100.0
        assert expense["category"] == "Food"

    def test_get_expense_by_id_wrong_user(self, app):
        from database.db import get_db

        uid1 = create_user("U1", "u1@u.com", "pass")
        uid2 = create_user("U2", "u2@u.com", "pass")
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (uid1, 100.0, "Food", "2023-01-01", "Dinner"),
            )
            eid = cursor.lastrowid

        # Test: Try to get uid1's expense using uid2
        expense = get_expense_by_id(eid, uid2)
        assert expense is None

    def test_get_expense_by_id_not_found(self, app):
        uid = create_user("User", "u@u.com", "pass")
        expense = get_expense_by_id(999, uid)
        assert expense is None

    def test_update_expense_success(self, app):
        from database.db import get_db

        uid = create_user("User", "u@u.com", "pass")
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (uid, 100.0, "Food", "2023-01-01", "Dinner"),
            )
            eid = cursor.lastrowid

        update_expense(eid, uid, 150.0, "Bills", "2023-01-02", "Updated Desc")

        with get_db() as conn:
            row = conn.execute("SELECT * FROM expenses WHERE id = ?", (eid,)).fetchone()
            assert row["amount"] == 150.0
            assert row["category"] == "Bills"
            assert row["date"] == "2023-01-02"
            assert row["description"] == "Updated Desc"

    def test_update_expense_wrong_user(self, app):
        from database.db import get_db

        uid1 = create_user("U1", "u1@u.com", "pass")
        uid2 = create_user("U2", "u2@u.com", "pass")
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (uid1, 100.0, "Food", "2023-01-01", "Dinner"),
            )
            eid = cursor.lastrowid

        # Attempt to update uid1's expense using uid2's ID
        update_expense(eid, uid2, 200.0, "Other", "2023-01-03", "Hacked")

        with get_db() as conn:
            row = conn.execute("SELECT * FROM expenses WHERE id = ?", (eid,)).fetchone()
            # Should remain unchanged
            assert row["amount"] == 100.0
            assert row["description"] == "Dinner"


# ------------------------------------------------------------------ #
# Integration Tests for Routes
# ------------------------------------------------------------------ #


class TestEditExpenseRoutes:
    def test_edit_expense_get_unauthenticated(self, client):
        response = client.get("/expenses/1/edit")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_edit_expense_get_authenticated_own(self, auth_client):
        from database.db import get_db

        with auth_client.session_transaction() as sess:
            uid = sess.get("user_id")

        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (uid, 50.0, "Food", "2023-01-01", "Lunch"),
            )
            eid = cursor.lastrowid

        response = auth_client.get(f"/expenses/{eid}/edit")
        assert response.status_code == 200
        assert b"Lunch" in response.data
        assert b"50" in response.data
        assert b"Food" in response.data

    def test_edit_expense_get_authenticated_others(self, auth_client):
        from database.db import get_db

        # Create another user and an expense for them
        create_user("Other", "other@test.com", "pass")
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (2, 50.0, "Food", "2023-01-01", "Lunch"),
            )
            eid = cursor.lastrowid

        response = auth_client.get(f"/expenses/{eid}/edit")
        assert response.status_code == 404

    def test_edit_expense_get_nonexistent(self, auth_client):
        response = auth_client.get("/expenses/9999/edit")
        assert response.status_code == 404

    def test_edit_expense_post_unauthenticated(self, client):
        response = client.post("/expenses/1/edit", data={})
        assert response.status_code == 302
        assert "/login" in response.location

    def test_edit_expense_post_success(self, auth_client):
        from database.db import get_db

        with auth_client.session_transaction() as sess:
            uid = sess.get("user_id")

        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (uid, 50.0, "Food", "2023-01-01", "Lunch"),
            )
            eid = cursor.lastrowid

        data = {
            "amount": "75.0",
            "category": "Transport",
            "date": "2023-01-02",
            "description": "Cab Ride",
        }
        response = auth_client.post(f"/expenses/{eid}/edit", data=data)

        assert response.status_code == 302
        assert "/profile" in response.location

        with get_db() as conn:
            row = conn.execute("SELECT * FROM expenses WHERE id = ?", (eid,)).fetchone()
            assert row["amount"] == 75.0
            assert row["category"] == "Transport"
            assert row["description"] == "Cab Ride"

    def test_edit_expense_post_others(self, auth_client):
        from database.db import get_db

        create_user("Other", "other@test.com", "pass")
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (2, 50.0, "Food", "2023-01-01", "Lunch"),
            )
            eid = cursor.lastrowid

        data = {
            "amount": "75.0",
            "category": "Transport",
            "date": "2023-01-02",
            "description": "Cab Ride",
        }
        response = auth_client.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "payload, expected_error",
        [
            (
                {
                    "amount": "",
                    "category": "Food",
                    "date": "2023-01-01",
                    "description": "x",
                },
                "Please enter a valid numeric amount",
            ),
            (
                {
                    "amount": "-10",
                    "category": "Food",
                    "date": "2023-01-01",
                    "description": "x",
                },
                "Amount must be greater than 0",
            ),
            (
                {
                    "amount": "10",
                    "category": "InvalidCat",
                    "date": "2023-01-01",
                    "description": "x",
                },
                "Please select a valid category",
            ),
            (
                {
                    "amount": "10",
                    "category": "Food",
                    "date": "not-a-date",
                    "description": "x",
                },
                "Please provide a valid date",
            ),
        ],
    )
    def test_edit_expense_post_invalid_data(self, auth_client, payload, expected_error):
        from database.db import get_db

        with auth_client.session_transaction() as sess:
            uid = sess.get("user_id")

        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (uid, 50.0, "Food", "2023-01-01", "Lunch"),
            )
            eid = cursor.lastrowid

        response = auth_client.post(f"/expenses/{eid}/edit", data=payload)
        assert response.status_code == 200
        assert expected_error.encode() in response.data

    def test_edit_expense_post_no_description(self, auth_client):
        from database.db import get_db

        with auth_client.session_transaction() as sess:
            uid = sess.get("user_id")

        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (uid, 50.0, "Food", "2023-01-01", "Lunch"),
            )
            eid = cursor.lastrowid

        data = {
            "amount": "60.0",
            "category": "Food",
            "date": "2023-01-01",
            "description": "",  # Empty description
        }
        response = auth_client.post(f"/expenses/{eid}/edit", data=data)

        assert response.status_code == 302
        assert "/profile" in response.location

        with get_db() as conn:
            row = conn.execute("SELECT * FROM expenses WHERE id = ?", (eid,)).fetchone()
            assert row["description"] is None
