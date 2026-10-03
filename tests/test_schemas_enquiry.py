from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas import EnquiryRequest

AEST = timezone(timedelta(hours=10))
REFERENCE = datetime(2026, 10, 11, 10, 0, 0, tzinfo=AEST)


def test_valid_whatsapp_request():
    req = EnquiryRequest(
        channel="whatsapp",
        from_phone="+61491570157",
        from_name="Priya",
        message="Hi, need a quote",
        received_at=REFERENCE,
    )
    assert req.channel.value == "whatsapp"
    assert req.from_name == "Priya"
    assert req.message == "Hi, need a quote"


def test_valid_web_form_request():
    req = EnquiryRequest(
        channel="web_form",
        from_phone="+61491570158",
        from_name=None,
        message="Please call me",
        received_at=REFERENCE,
    )
    assert req.channel.value == "web_form"
    assert req.from_name is None


def test_nullable_name_omitted():
    req = EnquiryRequest(
        channel="whatsapp",
        from_phone="+61491570159",
        message="Gutters please",
        received_at=REFERENCE,
    )
    assert req.from_name is None


def test_invalid_channel_rejected():
    with pytest.raises(ValidationError):
        EnquiryRequest(
            channel="sms",
            from_phone="+61491570157",
            message="Hello",
            received_at=REFERENCE,
        )


def test_received_at_must_be_timezone_aware():
    with pytest.raises(ValidationError):
        EnquiryRequest(
            channel="whatsapp",
            from_phone="+61491570157",
            message="Hello",
            received_at=datetime(2026, 10, 11, 10, 0, 0),
        )


def test_received_at_accepts_offset_aware():
    req = EnquiryRequest(
        channel="whatsapp",
        from_phone="+61491570157",
        message="Hello",
        received_at=datetime(2026, 10, 11, 0, 0, 0, tzinfo=timezone.utc),
    )
    assert req.received_at.tzinfo is not None


def test_message_content_not_altered():
    text = "  Keep spacing & punctuation!! "
    req = EnquiryRequest(
        channel="whatsapp",
        from_phone="+61491570157",
        message=text,
        received_at=REFERENCE,
    )
    assert req.message == text
