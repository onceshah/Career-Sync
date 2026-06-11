from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.auth.graph_auth import (
    get_auth_url,
    acquire_token_from_code
)

app = FastAPI(
    title="AI Email Triage System",
    version="1.0.0"
)


# --------------------------------------------------
# Health Check Endpoint
# --------------------------------------------------
# Used for:
# - Verifying FastAPI is running
# - Future Docker health checks
# - Monitoring
# --------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status": "running",
        "service": "AI Email Triage System"
    }


# --------------------------------------------------
# Login Endpoint
# --------------------------------------------------
# Redirects user to Microsoft Login Page
# --------------------------------------------------

@app.get("/login")
def login():

    auth_url = get_auth_url()

    return RedirectResponse(auth_url)


# --------------------------------------------------
# OAuth Callback Endpoint
# --------------------------------------------------
# Microsoft redirects here after successful login.
#
# Example:
# http://localhost:8000/auth/callback?code=XXXXX
#
# We capture the authorization code and
# exchange it for an access token.
# --------------------------------------------------

@app.get("/auth/callback")
def auth_callback(request: Request):

    code = request.query_params.get("code")
    """
    print("\n========== CALLBACK ==========")
    print("CODE:", code)
    """

    if not code:
        return {
            "error": "Authorization code missing"
        }

    token_response = acquire_token_from_code(code)

    return {
        "token_received": "access_token" in token_response,
        "token_length": len(token_response.get("access_token", "")),
    }

    """
    print("\n========== TOKEN RESPONSE ==========")
    print(token_response)
    """
    return token_response