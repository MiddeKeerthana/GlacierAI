from pathlib import Path

import requests
from dotenv import load_dotenv
import os


# ==========================================================
# PROJECT CONFIGURATION
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)


# ==========================================================
# COPERNICUS CONFIGURATION
# ==========================================================

CLIENT_ID = os.getenv("CDSE_CLIENT_ID")
CLIENT_SECRET = os.getenv("CDSE_CLIENT_SECRET")

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)

SENTINEL_HUB_URL = "https://sh.dataspace.copernicus.eu"


# ==========================================================
# VALIDATE CREDENTIALS
# ==========================================================

def validate_credentials():
    if not CLIENT_ID:
        raise RuntimeError(
            "CDSE_CLIENT_ID is missing from the .env file."
        )

    if not CLIENT_SECRET:
        raise RuntimeError(
            "CDSE_CLIENT_SECRET is missing from the .env file."
        )


# ==========================================================
# GET COPERNICUS ACCESS TOKEN
# ==========================================================

def get_access_token():
    """
    Request an OAuth2 access token from Copernicus Data Space.
    """

    validate_credentials()

    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.post(
        TOKEN_URL,
        data=payload,
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Copernicus authentication failed "
            f"(HTTP {response.status_code}): "
            f"{response.text}"
        )

    data = response.json()

    access_token = data.get("access_token")

    if not access_token:
        raise RuntimeError(
            "Copernicus response did not contain an access token."
        )

    return access_token


# ==========================================================
# TEST CONNECTION
# ==========================================================

def test_connection():
    """
    Test whether GlacierAI can successfully authenticate
    with Copernicus Data Space.
    """

    token = get_access_token()

    return {
        "connected": True,
        "message": "Successfully authenticated with Copernicus Data Space.",
        "token_received": bool(token),
    }


# ==========================================================
# MAIN TEST
# ==========================================================

if __name__ == "__main__":

    print()
    print("==========================================")
    print(" GLACIERAI - COPERNICUS CONNECTION TEST")
    print("==========================================")

    try:

        result = test_connection()

        print()
        print("Connection status :", "SUCCESS")
        print("Token received    :", result["token_received"])
        print()
        print("Copernicus authentication is working!")
        print()

    except Exception as error:

        print()
        print("Connection status :", "FAILED")
        print()
        print("Error:")
        print(error)
        print()