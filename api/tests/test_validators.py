from app.validators import (
    validate_phone,
    validate_gstin,
    validate_pan,
    mask_pan,
    cross_check_tax,
)


def test_indian_phone_validation():
    assert validate_phone("9820012345") is True
    assert validate_phone("+91 98200 12345") is True
    assert validate_phone("8765432109") is True
    assert validate_phone("7123456789") is True
    assert validate_phone("6123456789") is True

    # Invalid cases
    assert validate_phone("5123456789") is False
    assert validate_phone("12345") is False
    assert validate_phone("982001234567") is False


def test_gstin_and_pan_validation():
    valid_gstin = "27ABCDE1234F1Z5"
    valid_pan = "ABCDE1234F"

    assert validate_gstin(valid_gstin) is True
    assert validate_pan(valid_pan) is True

    assert validate_gstin("INVALIDGSTIN123") is False
    assert validate_pan("INVALIDPAN") is False


def test_pan_masking_security():
    pan = "ABCDE1234F"
    masked = mask_pan(pan)
    assert masked == "ABCDEXXXXF"
    assert "1234" not in masked


def test_tax_cross_check_consistency():
    # Maharashtra GST code is 27
    check = cross_check_tax("27ABCDE1234F1Z5", "ABCDE1234F", "Maharashtra")
    assert check["consistent"] is True
    assert check["state_match"] is True
    assert check["pan_match"] is True

    # State mismatch (27 is Maharashtra, not Karnataka)
    mismatch_state = cross_check_tax("27ABCDE1234F1Z5", "ABCDE1234F", "Karnataka")
    assert mismatch_state["consistent"] is False
    assert mismatch_state["state_match"] is False

    # PAN mismatch
    mismatch_pan = cross_check_tax("27ABCDE1234F1Z5", "XYZAB5678C", "Maharashtra")
    assert mismatch_pan["consistent"] is False
    assert mismatch_pan["pan_match"] is False
