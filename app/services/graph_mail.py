"""
Microsoft Graph Mail Service

Responsible for interacting with
Microsoft Graph Mail APIs.
"""
import requests

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

def get_messages(access_token: str):
    """
    Retrieve emails from Outlook mailbox
    using Microsoft Graph API.
    """

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        f"{GRAPH_BASE_URL}/me/messages",
        headers=headers
    )

    return response.json()