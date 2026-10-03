import pytest
import sqlite3
import os
from app import app as flask_app
from database.db import init_db
from datetime import datetime, timedelta

@pytest.fixture
def app():
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret',
        'WTF_CSRF_ENABLED': False,
    })

    import database.db
    original_path = database.db.DB_PATH
    database.db.DB_PATH = 'test_spendly.db'

    def mock_get_db():
        conn = sqlite3.connect(database.db.DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    database.db.get_db = mock_get_db

    with flask_app.app_context():
        init_db()
        yield flask_app

    # Cleanup
    if os.path.exists('test_spendly.db'):
        os.remove('test_spendly.db')
    database.db.get_db = lambda: sqlite3.connect(original_path)
    database.db.DB_PATH = original_path

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client):
    """A test client that is already logged in."""
    client.post('/register', data={'name': 'Test User', 'email': 'test@test.com', 'password': 'password', 'confirm_password': 'password'})
    client.post('/login', data={'email': 'test@test.com', 'password': 'password'})
    return client

@pytest.fixture
def seed_expenses(app):
    """Seeds expenses for a specific user across different dates."""
    from database.db import get_db
    conn = get_db()
    # Get the test user ID
    user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
    uid = user['id']

    today = datetime.now().date()

    expenses = [
        # Current Month
        (uid, 100.0, "Food", today.strftime("%Y-%m-%d"), "Lunch"),
        (uid, 50.0, "Transport", today.strftime("%Y-%m-%d"), "Taxi"),

        # 2 Months Ago
        (uid, 200.0, "Bills", (today - timedelta(days=60)).strftime("%Y-%m-%d"), "Electricity"),

        # 4 Months Ago
        (uid, 300.0, "Shopping", (today - timedelta(days=120)).strftime("%Y-%m-%d"), "Clothes"),

        # 7 Months Ago
        (uid, 400.0, "Health", (today - timedelta(days=210)).strftime("%Y-%m-%d"), "Doctor"),
    ]

    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses
    )
    conn.commit()
    return expenses

class TestDateFilter:

    def test_profile_auth_guard(self, client):
        """Unauthenticated requests to /profile should redirect to /login."""
        response = client.get('/profile')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_profile_unfiltered_view(self, auth_client, seed_expenses):
        """GET /profile with no params should show all expenses."""
        response = auth_client.get('/profile')
        assert response.status_code == 200
        # Total: 100+50+200+300+400 = 1050
        assert '₹1,050.00' in response.data.decode('utf-8')
        assert '5' in response.data.decode('utf-8') # Transaction count

    def test_profile_custom_date_filter_happy_path(self, auth_client, seed_expenses):
        """Filter by a valid date range should only show relevant expenses."""
        # Filter for only the most recent expenses (today)
        today = datetime.now().strftime("%Y-%m-%d")
        response = auth_client.get(f'/profile?date_from={today}&date_to={today}')

        assert response.status_code == 200
        # Total: 100+50 = 150
        assert '₹150.00' in response.data.decode('utf-8')
        assert '2' in response.data.decode('utf-8')

    def test_profile_preset_this_month(self, auth_client, seed_expenses):
        """'This Month' filter should only show current month expenses."""
        today = datetime.now()
        first_of_month = today.replace(day=1).strftime("%Y-%m-%d")
        end_of_month = today.strftime("%Y-%m-%d")

        response = auth_client.get(f'/profile?date_from={first_of_month}&date_to={end_of_month}')

        assert response.status_code == 200
        assert '₹150.00' in response.data.decode('utf-8')

    def test_profile_preset_last_3_months(self, auth_client, seed_expenses):
        """'Last 3 Months' filter should show expenses within 90 days."""
        today = datetime.now()
        start_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        response = auth_client.get(f'/profile?date_from={start_date}&date_to={end_date}')

        assert response.status_code == 200
        # Current month (150) + 2 months ago (200) = 350
        assert '₹350.00' in response.data.decode('utf-8')

    def test_profile_preset_last_6_months(self, auth_client, seed_expenses):
        """'Last 6 Months' filter should show expenses within 180 days."""
        today = datetime.now()
        start_date = (today - timedelta(days=180)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        response = auth_client.get(f'/profile?date_from={start_date}&date_to={end_date}')

        assert response.status_code == 200
        # Current (150) + 2mo (200) + 4mo (300) = 650
        assert '₹650.00' in response.data.decode('utf-8')

    def test_profile_date_validation_start_after_end(self, auth_client, seed_expenses):
        """date_from > date_to should flash error and show unfiltered view."""
        response = auth_client.get('/profile?date_from=2026-12-01&date_to=2026-01-01')

        assert response.status_code == 200
        assert 'Start date must be before end date.' in response.data.decode('utf-8')
        # Should fall back to unfiltered (1050)
        assert '₹1,050.00' in response.data.decode('utf-8')

    def test_profile_malformed_dates(self, auth_client, seed_expenses):
        """Malformed date strings should silently fall back to unfiltered view."""
        response = auth_client.get('/profile?date_from=not-a-date&date_to=2026-10-01')

        assert response.status_code == 200
        assert '₹1,050.00' in response.data.decode('utf-8')

    def test_profile_empty_range(self, auth_client, seed_expenses):
        """A date range with no expenses should show ₹0.00."""
        # Range in 1990
        response = auth_client.get('/profile?date_from=1990-01-01&date_to=1990-01-31')

        assert response.status_code == 200
        assert '₹0.00' in response.data.decode('utf-8')
        assert '0' in response.data.decode('utf-8') # 0 transactions
        assert 'Food' not in response.data.decode('utf-8')
        assert 'Transport' not in response.data.decode('utf-8')

    def test_profile_integration_filtering(self, auth_client, seed_expenses):
        """Verify that summary stats, transactions, and categories are all filtered."""
        today = datetime.now().strftime("%Y-%m-%d")
        response = auth_client.get(f'/profile?date_from={today}&date_to={today}')

        # 1. Summary Stats
        assert '₹150.00' in response.data.decode('utf-8')

        # 2. Transaction List (Only today's should be there)
        assert 'Lunch' in response.data.decode('utf-8')
        assert 'Taxi' in response.data.decode('utf-8')
        assert 'Electricity' not in response.data.decode('utf-8') # 2 months ago

        # 3. Category Breakdown (Only Food and Transport)
        assert 'Food' in response.data.decode('utf-8')
        assert 'Transport' in response.data.decode('utf-8')
        assert 'Bills' not in response.data.decode('utf-8') # 2 months ago
