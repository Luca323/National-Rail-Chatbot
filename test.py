import pytest
from datetime import datetime, timedelta
from NLPU import (parse_date, parse_time, get_station, check_ticket,
                  railcard_choice, build_datetime)
from PredictionModel import encode, select_routes
from API import NationalRailAPI

"""INPUT TESTS"""

#check tomorrow gets turned into the right date
def test_parse_date_tomorrow():
    expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert parse_date("travelling tomorrow") == expected

#iso date should just pass straight through
def test_parse_date_iso():
    assert parse_date("on 2026-06-15") == "2026-06-15"

#written out dates like 20th april
def test_parse_date_month_name():
    assert parse_date("20th April 2026") == "2026-04-20"

#nonsense input shouldnt return a date
def test_parse_date_invalid():
    assert parse_date("at some point") is None

#3pm in 24hr time
def test_parse_time_pm():
    assert parse_time("at 3pm") == "15:00"

#24hr time stays the same
def test_parse_time_24h():
    assert parse_time("at 14:30") == "14:30"

#12am = midnight
def test_parse_time_midnight():
    assert parse_time("12am") == "00:00"

#norwich should give NRW
def test_get_station_norwich():
    assert get_station("travel to Norwich") == "NRW"

#made up place gives nothing
def test_get_station_unknown():
    assert get_station("travel to Atlantis") is None

#spotting a return ticket
def test_check_ticket_return():
    assert check_ticket("I want a return ticket") == "return"

#no ticket word means none
def test_check_ticket_none():
    assert check_ticket("hello there") is None

#senior railcard detection
def test_railcard_senior():
    assert railcard_choice("I have a senior railcard") == "senior"

#stick date and time together
def test_build_datetime():
    assert build_datetime("2026-06-15", "3pm") == "2026-06-15T15:00:00"

"""PREDICTION TESTS"""

#station thats not in the encoder should blow up
def test_encode_unknown_station_raises():
    with pytest.raises(ValueError):
        encode(["NOT_A_REAL_STATION"])

#no route connecting these so it should error
def test_select_routes_no_valid_route_raises():
    fake_routes = {0: [1, 2, 3]}
    with pytest.raises(ValueError):
        select_routes(99, 100, fake_routes)

#1 comes before 3 so this is a valid route
def test_select_routes_returns_valid():
    fake_routes = {0: [1, 2, 3]}
    result = select_routes(1, 3, fake_routes)
    assert [1, 2, 3] in result

#going backwards along the route isnt allowed
def test_select_routes_wrong_order_raises():
    fake_routes = {0: [1, 2, 3]}
    with pytest.raises(ValueError):
        select_routes(3, 1, fake_routes)

"""API TESTS"""

#fake response with no journeys in it
EMPTY_XML = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:ns2="http://www.thalesgroup.com/ojp/jpdlr"
               xmlns:ns3="http://www.thalesgroup.com/ojp/common">
  <soap:Body><ns2:Response></ns2:Response></soap:Body>
</soap:Envelope>"""


#just making sure the url is the right one
def test_api_has_correct_url():
    api = NationalRailAPI()
    assert api.url == "https://ojp.nationalrail.co.uk/webservices"

#empty xml should give back an empty list not crash
def test_parse_journeys_empty_returns_list():
    result = NationalRailAPI.parse_journeys(EMPTY_XML)
    assert result == []