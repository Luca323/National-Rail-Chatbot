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

    def get_journey(self, origin_crs: str, destination_crs: str, datetime_str: str, adults: int = 1, children: int = 0):
        #Take origin, destination and datetime and perform lookup on SOAP API

        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:jpd="http://www.thalesgroup.com/ojp/jpdlr"
                  xmlns:com="http://www.thalesgroup.com/ojp/common">
  <soapenv:Header/>
  <soapenv:Body>
    <jpd:RealtimeJourneyPlanRequest>

      <jpd:origin>
        <com:stationCRS>{origin_crs}</com:stationCRS>
      </jpd:origin>

      <jpd:destination>
        <com:stationCRS>{destination_crs}</com:stationCRS>
      </jpd:destination>

      <jpd:realtimeEnquiry>STANDARD</jpd:realtimeEnquiry>

      <jpd:outwardTime>
        <jpd:departBy>{datetime_str}</jpd:departBy>
      </jpd:outwardTime>

      <jpd:directTrains>false</jpd:directTrains>

      <jpd:fareRequestDetails>
        <jpd:passengers>
          <com:adult>{adults}</com:adult>
          <com:child>{children}</com:child>
        </jpd:passengers>
        <jpd:fareClass>STANDARD</jpd:fareClass>
      </jpd:fareRequestDetails>

      <jpd:includeAdditionalInformation>true</jpd:includeAdditionalInformation>

    </jpd:RealtimeJourneyPlanRequest>
  </soapenv:Body>
</soapenv:Envelope>
"""

        response = requests.post(
            self.url,
            data=envelope.encode("utf-8"),
            headers=self.headers,
            auth=self.auth,
        )

        return response.text

    @staticmethod
    def parse_journeys(xml_string):
        import xml.etree.ElementTree as ET

        ns = {
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
            'ns2': 'http://www.thalesgroup.com/ojp/jpdlr',
            'ns3': 'http://www.thalesgroup.com/ojp/common'
        }

        root = ET.fromstring(xml_string)
        journeys = []

        for journey in root.findall('.//ns2:outwardJourney', ns):

            dep = journey.find('.//ns2:timetable/ns2:scheduled/ns2:departure', ns)
            arr = journey.find('.//ns2:timetable/ns2:scheduled/ns2:arrival', ns)

            legs = journey.findall('.//ns2:leg', ns)

            # Count changes
            train_legs = [l for l in legs if l.find('ns2:mode', ns).text == 'TRAIN']
            num_changes = max(len(train_legs) - 1, 0)

            #structure the fares
            fares = []
            for fare in journey.findall('ns2:fare', ns):
                price = fare.find('ns3:totalPrice', ns)
                desc = fare.find('ns3:description', ns)

                fares.append({
                    "description": desc.text if desc is not None else None,
                    "price_pence": int(price.text) if price is not None else None                })

            # Journey legs
            parsed_legs = []
            for leg in legs:
                parsed_legs.append({
                    "from": leg.find('ns2:board/ns2:crsCode', ns).text,
                    "to": leg.find('ns2:alight/ns2:crsCode', ns).text,
                    "mode": leg.find('ns2:mode', ns).text,
                })

            journeys.append({
                "departure": dep.text if dep is not None else None,
                "arrival": arr.text if arr is not None else None,
                "changes": num_changes,
                "fares": fares,  # just return all fares as-is
                "legs": parsed_legs
            })

        return journeys

class LlamaWrapper:
    def __init__(self, base_url="http://localhost:8080"):
        self.url = f"{base_url}/completion"

    def generate(self, prompt, max_tokens=200, temperature=0.7):
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "stop": ["User:", "\n\n"]
        }

        response = requests.post(self.url, json=payload)

        if response.status_code != 200:
            raise Exception(f"LLM error: {response.text}")

        data = response.json()
        return data.get("content", "").strip()


if __name__ == "__main__":

    llama = LlamaWrapper()

    #Example for how to use LLM prompt formatting, the model I've downloaded is lightweight so be specific
    prompt = '''
    You are a helpful train assistant.

    Use ONLY the provided data to answer the question.
    
    Data:
    free train to Norwich at tomorrow at 14:00.
    free train to Norwich at tomorrow at 15:00.
    free train to Norwich at tomorrow at 17:00.
    
    
    User: When is the next train to Norwich?
    Assistant:
    '''

    response = llama.generate(prompt)

    print(response)


    '''api = NationalRailAPI()
    response = api.get_journey("LST", "NRW", "2026-04-14T10:00:00")

    print(api.parse_journeys(response))'''
