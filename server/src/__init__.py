"""Browser Farm - Distributed Browser Automation Platform"""

__version__ = "1.0.0"

from .models import Profile, ProxyConfig, Account

__all__ = ["Profile", "ProxyConfig", "Account"]


def get_account(account_id: str) -> dict:
    """
    Get account credentials at runtime.
    This function is injected by the server when running user scripts.
    """
    import os
    import json

    accounts_json = os.environ.get("BROWSER_FARM_ACCOUNTS", "{}")
    accounts = json.loads(accounts_json)

    if account_id not in accounts:
        raise ValueError(f"Account {account_id} not found")

    return accounts[account_id]
