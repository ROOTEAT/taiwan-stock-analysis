from twstock_lab.cloud_storage import (
    hash_password,
    normalize_username,
    validate_username,
    verify_password,
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
