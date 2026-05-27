import experta_re
from experta_re import get_response, get_startup_msg

#fresh engine since otherwise engine is kept across tests which bad for testing
def fresh_engine():
    experta_re.engine.reset()
    experta_re.engine._replies = []


#booking intent should start things off and ask where from
def test_booking_starts_and_asks_origin():
    fresh_engine()
    replies = get_response("I want to book a ticket")
    assert any("travel" in r.lower() or "from" in r.lower() for r in replies)

#from and to in one go should both get picked up
def test_from_to_extracted_in_one_message():
    fresh_engine()
    replies = get_response("I want to travel from Norwich to London")
    joined = " ".join(replies).lower()
    assert "travel from" not in joined

#whole booking flow until it asks to confirm
def test_full_booking_reaches_confirmation():
    fresh_engine()
    get_response("I want to book a ticket")
    get_response("from Norwich")
    get_response("to London")
    get_response("one way")
    get_response("tomorrow")
    get_response("at 10am")
    replies = get_response("no")
    joined = " ".join(replies).lower()
    assert "search" in joined or "here's what i have" in joined

#delay should switch out of booking and ask where you are
def test_delay_intent_switches_mode():
    fresh_engine()
    replies = get_response("my train is delayed")
    assert any("currently" in r.lower() for r in replies)

#delay flow far enough that it asks for the reason code
def test_delay_flow_asks_for_reason():
    fresh_engine()
    get_response("my train is delayed")
    get_response("Southampton Central")
    get_response("Clapham Junction")
    replies = get_response("10")
    joined = " ".join(replies).lower()
    assert "reason" in joined
