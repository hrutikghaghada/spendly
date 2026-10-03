from datetime import datetime, timedelta

def calculate_date_presets():
    """
    Calculates date ranges for the profile page presets.
    Returns a dictionary of {preset_name: {'from': date_str, 'to': date_str}}
    """
    today = datetime.now().date()

    # This Month: 1st of current month to today
    this_month_start = today.replace(day=1).strftime("%Y-%m-%d")
    this_month_end = today.strftime("%Y-%m-%d")

    # Last 3 Months: 90 days ago to today
    three_month_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    three_month_end = today.strftime("%Y-%m-%d")

    # Last 6 Months: 180 days ago to today
    six_month_start = (today - timedelta(days=180)).strftime("%Y-%m-%d")
    six_month_end = today.strftime("%Y-%m-%d")

    return {
        "this_month": {"from": this_month_start, "to": this_month_end},
        "three_months": {"from": three_month_start, "to": three_month_end},
        "six_months": {"from": six_month_start, "to": six_month_end},
    }

def validate_date_range(date_from, date_to):
    """
    Validates date strings and ensures chronological order.
    Preserves valid dates even if the opposing field is malformed.

    Returns: (validated_from, validated_to, error_message)
    """
    validated_from = None
    validated_to = None
    error = None

    if date_from:
        try:
            datetime.strptime(date_from, "%Y-%m-%d")
            validated_from = date_from
        except ValueError:
            pass # Silently ignore malformed date_from

    if date_to:
        try:
            datetime.strptime(date_to, "%Y-%m-%d")
            validated_to = date_to
        except ValueError:
            pass # Silently ignore malformed date_to

    # Logical range validation: only if both are valid
    if validated_from and validated_to and validated_from > validated_to:
        return None, None, "Start date must be before end date."

    return validated_from, validated_to, error
