from twstock_lab.cloud_storage import (
    hash_password,
    normalize_username,
    sign_session_token,
    validate_username,
    verify_password,
    verify_session_token,
)


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("correct-horse")
    second = hash_password("correct-horse")
    assert first != second
    assert verify_password("correct-horse", first)
    assert not verify_password("wrong-password", first)


def test_username_normalization_and_validation():
    assert normalize_username("  New_User ") == "new_user"
    assert validate_username("New_User") == "new_user"


def test_invalid_username_rejected():
    try:
        validate_username("中文")
    except ValueError as exc:
        assert "3–32" in str(exc)
    else:
        raise AssertionError("invalid username should fail")


def test_session_token_uses_sliding_24_hour_idle_window():
    user_id = "7f15ef07-d86e-4ee8-98a6-c36e8984f616"
    secret = "a-cookie-secret-that-is-longer-than-32-characters"
    token = sign_session_token(user_id, "new_user", secret, now=1_000)
    restored = verify_session_token(token, secret, now=1_000 + 86_399)
    assert restored == {"id": user_id, "username": "new_user", "active": 1_000}
    assert verify_session_token(token, secret, now=1_000 + 86_401) is None


def test_session_token_rejects_tampering():
    token = sign_session_token(
        "7f15ef07-d86e-4ee8-98a6-c36e8984f616",
        "new_user",
        "a-cookie-secret-that-is-longer-than-32-characters",
        now=1_000,
    )
    assert (
        verify_session_token(
            token + "x",
            "a-cookie-secret-that-is-longer-than-32-characters",
            now=1_001,
        )
        is None
    )
