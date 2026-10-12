"""Voting tokens: how they are made, written, cleaned up and hashed.

A token looks like  K7M2-9QXP  on the paper slip (8 characters plus a hyphen
so it is easier to read). The database never stores the token itself, only its
SHA-256 hash, so even someone who copies the database cannot read the tokens.
"""
import hashlib
import secrets

# 31 characters. We left out 0, O, 1, I and L because they look alike on a
# printed slip and voters would mistype them.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
TOKEN_LENGTH = 8


def generate_token():
    """Make one random token, such as 'K7M2-9QXP'.

    We use the `secrets` module, not `random`: `random` is predictable,
    `secrets` is built for passwords and tokens.
    """
    raw = "".join(secrets.choice(ALPHABET) for _ in range(TOKEN_LENGTH))
    return raw[:4] + "-" + raw[4:]


def normalize_token(text):
    """Clean what a voter typed: ignore spaces and hyphens, ignore upper/lower case.

    'k7m2 9qxp', 'K7M2-9QXP' and 'k7m29qxp' all become 'K7M29QXP'.
    """
    return "".join(text.split()).replace("-", "").upper()


def hash_token(text):
    """Return the SHA-256 hash (64 hex characters) of a token.

    The text is normalized first, so every way of typing the same token
    gives the same hash.
    """
    return hashlib.sha256(normalize_token(text).encode("utf-8")).hexdigest()
