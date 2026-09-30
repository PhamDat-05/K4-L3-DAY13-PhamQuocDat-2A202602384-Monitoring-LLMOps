from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrubber_keeps_hex_trace_ids_intact() -> None:
    trace_id = "78ec2e146f17a0958734526e26df8bc8"
    assert scrub_text(trace_id) == trace_id


def test_scrub_cccd_and_credit_card() -> None:
    out = scrub_text("CCCD 079123456789 and card 4111 1111 1111 1111")
    assert "079123456789" not in out
    assert "4111 1111 1111 1111" not in out
    assert "REDACTED_CCCD" in out
    assert "REDACTED_CREDIT_CARD" in out
