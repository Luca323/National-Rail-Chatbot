import os
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime


class NationalRailAPI:
    def __init__(self):
        self.url = "https://ojp.nationalrail.co.uk/webservices"  # NOT the .wsdl URL
        self.auth = HTTPBasicAuth('wwang', '?i92S6')
        self.headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "",
        }

    def get_journey(self, origin_crs: str, destination_crs: str, datetime_str: str):
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

        print(response.status_code)
        print(response.text)
        return response.text


if __name__ == "__main__":
    api = NationalRailAPI()
    api.get_journey("KGX", "MAN", "2026-04-04T10:00:00")
