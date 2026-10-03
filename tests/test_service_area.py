from app.tools.service_area import check_service_area


def test_supported_paddington(seeded_session):
    result = check_service_area(seeded_session, "4064")
    assert result.in_area is True
    assert result.canonical_suburb == "Paddington"


def test_supported_toowong(seeded_session):
    result = check_service_area(seeded_session, "4066")
    assert result.in_area is True
    assert result.canonical_suburb == "Toowong"


def test_springfield_4300_out_of_area(seeded_session):
    result = check_service_area(seeded_session, "4300")
    assert result.in_area is False
    assert result.canonical_suburb is None


def test_arbitrary_unsupported_postcode(seeded_session):
    result = check_service_area(seeded_session, "9999")
    assert result.in_area is False


def test_suburb_text_does_not_decide_area(seeded_session):
    # Exact postcode only — suburb string is irrelevant to this tool.
    result = check_service_area(seeded_session, "Paddington")
    assert result.in_area is False
