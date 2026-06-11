import os

from dotenv import load_dotenv
from msal import ConfidentialClientApplication

load_dotenv()

TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

ACCESS_TOKEN = None


AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

SCOPES = [
    "User.Read",
    "Mail.Read"
]

app = ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
    authority=AUTHORITY
)


def get_auth_url():
    """
    Generates Microsoft login URL.
    """

    return app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )


# --------------------------------------------------
# Exchange Authorization Code for Access Token
# --------------------------------------------------
#
# Microsoft sends an authorization code
# to our callback endpoint.
#
# This function exchanges that code for:
# - Access Token
# - ID Token
# - Expiry Information
#
# --------------------------------------------------

def acquire_token_from_code(code: str):

    #print("acquire_token_from_code called")

    global ACCESS_TOKEN

    token_response = app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    ACCESS_TOKEN = token_response.get("access_token")

    #print("Token Stored:", ACCESS_TOKEN is not None)

    return token_response