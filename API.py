import os
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import xml.etree.ElementTree as ET

class NationalRailAPI:
    def __init__(self):
        self.url = "https://ojp.nationalrail.co.uk/webservices"
        self.auth = HTTPBasicAuth('wwang', '?i92S6') #NDA credentials
        self.headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "",
        }

    def get_journey(self, origin_crs: str, destination_crs: str, datetime_str: str):
        #Take origin, destination and datetime and perform lookup on SOAP API

        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
                        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                                          xmlns:ojp="http://www.thalesgroup.com/ojp/jpservices"
                                          xmlns:common="http://www.thalesgroup.com/ojp/common">
                          <soapenv:Header/>
                          <soapenv:Body>
                            <ojp:RealtimeJourneyPlanRequest>
                              <ojp:origin>
                                <common:stationCRS>{origin_crs}</common:stationCRS>
                              </ojp:origin>
                              <ojp:destination>
                                <common:stationCRS>{destination_crs}</common:stationCRS>
                              </ojp:destination>
                              <ojp:realtimeEnquiry>STANDARD</ojp:realtimeEnquiry>
                              <ojp:outwardTime>
                                <ojp:departBy>{datetime_str}</ojp:departBy>
                              </ojp:outwardTime>
                              <ojp:directTrains>false</ojp:directTrains>
                            </ojp:RealtimeJourneyPlanRequest>
                          </soapenv:Body>
                        </soapenv:Envelope>"""

        response = requests.post(
            self.url,
            data=envelope.encode("utf-8"),
            headers=self.headers,
            auth=self.auth,
        )

        return response.text

    @staticmethod
    def parse_journeys(xml_string):
        #Take XML response and return data in readable format

        ns = {
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
            'ns2': 'http://www.thalesgroup.com/ojp/jpservices',
            'ns3': 'http://www.thalesgroup.com/ojp/common'
        }

        root = ET.fromstring(xml_string)

        journeys = []

        for journey in root.findall('.//ns2:outwardJourney', ns):
            dep = journey.find('.//ns2:scheduled/ns2:departure', ns)
            arr = journey.find('.//ns2:scheduled/ns2:arrival', ns)

            legs = journey.findall('.//ns2:leg', ns)

            num_changes = len([l for l in legs if l.find('ns2:mode', ns).text == 'TRAIN']) - 1

            journey_info = {
                "departure": dep.text if dep is not None else None,
                "arrival": arr.text if arr is not None else None,
                "changes": max(num_changes, 0),
                "legs": []
            }

            for leg in legs:
                journey_info["legs"].append({
                    "from": leg.find('ns2:board', ns).text,
                    "to": leg.find('ns2:alight', ns).text,
                    "mode": leg.find('ns2:mode', ns).text
                })

            journeys.append(journey_info)

        return journeys


if __name__ == "__main__":
    api = NationalRailAPI()
    response = api.get_journey("LST", "NRW", "2026-04-05T10:00:00")

    print(api.parse_journeys(response))
