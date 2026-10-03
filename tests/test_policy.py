from app.tools.policy import get_policies, get_policy


def test_policy_topics_present(seeded_session):
    policies = get_policies(seeded_session)
    for topic in (
        "business",
        "office_hours",
        "emergency",
        "services_offered",
        "services_not_offered",
        "quote_policy",
        "warranty_policy",
        "insurance_policy",
    ):
        assert topic in policies


def test_emergency_and_warranty_facts(seeded_session):
    emergency = get_policy(seeded_session, "emergency")
    assert emergency["phone_display"] == "0491 570 110"
    assert "Water actively entering the home" in emergency["definition"]

    warranty = get_policy(seeded_session, "warranty_policy")
    assert warranty["workmanship_restorations_years"] == 7
    assert warranty["workmanship_replacements_years"] == 10
    assert warranty["no_other_warranty_may_be_promised"] is True


def test_unsupported_services_exact(seeded_session):
    not_offered = get_policy(seeded_session, "services_not_offered")
    assert "Solar panels" in not_offered
    assert any("Asbestos" in item for item in not_offered)
