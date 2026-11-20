"""Phase 19: print a NEW pair of secrets for the live site. Run it, paste both values into the host's
environment settings (Render), and do not reuse them anywhere else, including backend/.env:

    python3 scripts/generate-prod-secrets.py

JWT_SECRET_KEY signs login tokens; TOKEN_ENCRYPTION_KEY encrypts stored GitHub tokens (a Fernet key).
Changing either later logs everyone out (they just log in again). Only the Python standard library.
"""
import base64
import os
import secrets

print("JWT_SECRET_KEY=" + secrets.token_urlsafe(48))
print("TOKEN_ENCRYPTION_KEY=" + base64.urlsafe_b64encode(os.urandom(32)).decode())
