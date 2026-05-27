from API import NationalRailAPI
from NLPU import (intention_by_keyword, extract_time_date, extract_stations,
                  check_ticket, railcard_choice, re,
                  parse_time, parse_date, build_datetime)
from PredictionModel import extract_routes, pd, predict_delay
from datetime import datetime
import collections
import collections.abc
for type_name in ['Mapping','MutableMapping','Iterable','MutableSet']:
    if not hasattr(collections, type_name):
        setattr(collections, type_name, getattr(collections.abc, type_name))
from experta import *

api = NationalRailAPI()

ROUTES = extract_routes(pd.read_csv('dataset.csv')['location']) #Loaded earlier to prevent later overhead

SLOT_PROMPTS = {
    "origin": "Where would you like to travel from?",
    "destination": "Where would you like to travel to?",
    "date": "What date would you like to travel?",
    "time": "What time would you like to depart?",
    "ticket_type": "Would you like a one-way, return, or open return ticket?",
    "return_date": "What date would you like to return?",
    "return_time": "What time would you like to return?",
}

DELAY_PROMPTS = {
    "origin": "Where are you currently?",
    "destination": "Where are you travelling to?",
    "current_delay": "How many minutes late is your train currently?",
    "reason": "Do you have the delay reason code?"
}

RAILCARD_PROMPT = (
    "Do you have a railcard? "
    "(16-17, 16-25, 26-30, disabled, family & friends, network, senior, "
    "two together, veterans — or 'no')"
)

def get_discount(railcard):
    if railcard == "16-17":
        return 0.5
    elif railcard != None and railcard != "16-17":
        return 1/3
    return 0


class UserInput(Fact):
    text = Field(str, mandatory=True)

class Intent(Fact):
    value = Field(str, mandatory=True)

class Booking(Fact):
    origin       = Field(object,  default=None)
    destination  = Field(object,  default=None)
    date         = Field(object,  default=None)
    time         = Field(object,  default=None)
    ticket_type  = Field(object,  default=None)
    return_date  = Field(object,  default=None)
    return_time  = Field(object,  default=None)
    adults       = Field(int,  default=1)
    children     = Field(int,  default=0)
    railcard     = Field(object,  default=None)


class AskingFor(Fact):
    slot = Field(str, mandatory=True)

class RailcardAsked(Fact):  pass
class AwaitingConfirm(Fact): pass
class BookingComplete(Fact): pass
class SessionDone(Fact):     pass
class Delayed(Fact): pass

class DelayJourney(Fact):
    origin = Field(str, default=None)
    destination = Field(str, default=None)
    current_delay = Field(int, default=None)
    reason = Field(int, default=None)

class DelayPrediction(Fact):
    minutes = Field(float, mandatory=True)

class BookingEngine(KnowledgeEngine):

    @Rule(Intent(value='greeting'), salience=100)
    def handle_greeting(self):
        self.reply("Hello! I can help you find the cheapest train ticket.")
        self.retract_by_type(Intent)

    @Rule(Intent(value="thanks"), salience=100)
    def handle_thanks(self):
        self.reply("You're welcome!")
        self.retract_by_type(Intent)

    @Rule(Intent(value="goodbye"), salience=100)
    def handle_goodbye(self):
        self.reply("")
        self.declare(SessionDone())
        self.retract_by_type(Intent)

    @Rule(Intent(value="delay"), salience=100)
    def handle_delay(self):
        self.retract_by_type(Booking)
        self.retract_by_type(BookingComplete)
        self.retract_by_type(RailcardAsked)
        self.declare(DelayJourney())
        self.retract_by_type(Intent)

    @Rule(Intent(value="book"),NOT(DelayJourney()) , NOT(Booking()), salience=90)
    def start_booking(self):
        self.declare(Booking())
        self.retract_by_type(Intent)

    @Rule(AS.ui << UserInput(text=MATCH.text), NOT(Booking()), NOT(Delayed()),
          NOT(DelayJourney()), NOT(Intent(value="goodbye")), salience=95)
    def auto_start_booking(self, ui, text):
        self.retract(ui)
        self.declare(Booking())
        self.declare(UserInput(text=text))

    @Rule(
        AS.ui << UserInput(text=MATCH.text), AS.bk << Booking(),
        salience=96
    )
    def extract_entities(self, ui, bk, text):
        updates = {}

        # ── Ticket type ──────────────────────────────────────────────────────────
        if not bk["ticket_type"]:
            tt = check_ticket(text)
            if tt:
                updates["ticket_type"] = tt

        # Dates and time
        spacy_dates, spacy_times = extract_time_date(text)
        parsed_date = next((parse_date(d) for d in spacy_dates if parse_date(d)), None)
        if not parsed_date:
            parsed_date = parse_date(text)

        parsed_time = next((parse_time(t) for t in spacy_times if parse_time(t)), None)
        if not parsed_time:
            parsed_time = parse_time(text)

        asking = self.current_asking()

        # Use updates["ticket_type"] if bk["ticket_type"] hasn't been set yet
        effective_ticket_type = bk["ticket_type"] or updates.get("ticket_type")

        is_return_context = (
                effective_ticket_type == "return"
                and bk["date"]
                and asking in ("return_date", "return_time")
        )

        if is_return_context:
            if parsed_date and not bk["return_date"]:
                updates["return_date"] = parsed_date
            if parsed_time and not bk["return_time"]:
                updates["return_time"] = parsed_time
        else:
            if parsed_date and not bk["date"]:
                updates["date"] = parsed_date
            if parsed_time and not bk["time"]:
                updates["time"] = parsed_time

            # double check
            if effective_ticket_type == "return" and (bk["time"] or updates.get("time")):
                all_times = [parse_time(t) for t in spacy_times if parse_time(t)]
                if len(all_times) >= 2 and not bk["return_time"]:
                    updates["return_time"] = all_times[1]

        # Stations
        if not bk["origin"] or not bk["destination"]:
            o_crs, d_crs = extract_stations(text, asking)

            if not d_crs and not bk["destination"]:
                to_match = re.search(r'\bto\s+([a-zA-Z\s]+?)(?:\s+from|\s+on|\s+at|\s+\d|$)', text, re.I)
                if to_match:
                    _, d_crs = extract_stations(to_match.group(1).strip(), "destination")

            if not o_crs and not bk["origin"]:
                from_match = re.search(r'\bfrom\s+([a-zA-Z\s]+?)(?:\s+to|\s+on|\s+at|\s+\d|$)', text, re.I)
                if from_match:
                    o_crs, _ = extract_stations(from_match.group(1).strip(), "origin")

            if o_crs and not bk["origin"]:
                updates["origin"] = o_crs
            if d_crs and not bk["destination"]:
                updates["destination"] = d_crs

        # passengers
        am = re.search(r"(\d+)\s+adult", text, re.I)
        cm = re.search(r"(\d+)\s+child", text, re.I)
        if am:
            updates["adults"] = int(am.group(1))
        if cm:
            updates["children"] = int(cm.group(1))

        if updates:
            self.modify(bk, **updates)
            self.retract_by_type(AskingFor)

        self.retract(ui)

    def current_asking(self):
        for fact in self.facts.values():
            if isinstance(fact, AskingFor):
                return fact["slot"]
        return None

    def reply(self, msg):
        self._replies.append(msg)

    #Removes facts as needed
    def retract_by_type(self, fact_class):
        for fid, fact in list(self.facts.items()):
            if isinstance(fact, fact_class):
                self.retract(fact)

    def ask_slot(self, slot):
        if self.current_asking() != slot:
            self.retract_by_type(AskingFor)
            self.declare(AskingFor(slot=slot))
            self.reply(SLOT_PROMPTS[slot])

    @Rule(Booking(origin=None),NOT(DelayJourney()), NOT(AskingFor()), NOT(AwaitingConfirm()),salience = 70)
    def ask_origin(self):
        self.ask_slot(slot='origin')

    @Rule(Booking(destination=None),NOT(DelayJourney()), NOT(Booking(origin=None)),
          NOT(AskingFor()), NOT(AwaitingConfirm()), salience=69)
    def ask_destination(self):
        self.ask_slot(slot='destination')

    @Rule(Booking(ticket_type=None),NOT(DelayJourney()), NOT(Booking(origin=None)), NOT(Booking(destination=None)),
          NOT(AskingFor()), NOT(AwaitingConfirm()), salience=68)
    def ask_ticket_type(self):
        self.ask_slot(slot="ticket_type")

    @Rule(Booking(date=None),NOT(DelayJourney()), NOT(Booking(ticket_type=None)),
          NOT(AskingFor()), NOT(AwaitingConfirm()), salience=67)
    def ask_date(self):
        self.ask_slot(slot="date")

    @Rule(Booking(time=None),NOT(DelayJourney()), NOT(Booking(date=None)),
          NOT(AskingFor()), NOT(AwaitingConfirm()), salience=66)
    def ask_time(self):
        self.ask_slot(slot="time")

    @Rule(AS.bk << Booking(ticket_type="return", return_date=None),
          NOT(Booking(time=None)),
          NOT(AskingFor()), NOT(AwaitingConfirm()), salience=65)
    def ask_return_date(self, bk):
        self.ask_slot(slot="return_date")

    @Rule(AS.bk << Booking(ticket_type="return", return_time=None),
          NOT(Booking(return_date=None)),
          NOT(AskingFor()), NOT(AwaitingConfirm()), salience=64)
    def ask_return_time(self, bk):
        self.ask_slot(slot="return_time")

    #Railcard logic after all conditions for booking are met
    @Rule(
        Booking(origin=MATCH.o, destination=MATCH.d, date=MATCH.dt,
                time=MATCH.tm, ticket_type=MATCH.tt),
        NOT(Booking(origin=None)), NOT(Booking(destination=None)),
        NOT(Booking(date=None)), NOT(Booking(time=None)),
        NOT(Booking(ticket_type=None)),
        NOT(RailcardAsked()),
        NOT(AwaitingConfirm()),
        NOT(AskingFor()),
        salience=60
    )
    def ask_railcard(self, o, d, dt, tm, tt):
        self.declare(RailcardAsked())
        self.declare(AskingFor(slot="railcard"))
        self.reply(RAILCARD_PROMPT)

    @Rule(
        AS.ui << UserInput(text=MATCH.text),
        AskingFor(slot="railcard"),
        AS.bk << Booking(),
        salience=97
    )
    def handle_railcard_answer(self, ui, bk, text):
        no_words = ("no", "none", "don't", "dont", "haven't", "havent", "n/a")
        railcard = None if any(w in text.lower() for w in no_words) else railcard_choice(text)
        self.modify(bk, railcard=railcard)
        self.retract(ui)
        self.retract_by_type(AskingFor)


    #Delay Logic

    @Rule(DelayJourney(origin=None), NOT(AskingFor()),salience=80)
    def ask_delay_origin(self):
        self.declare(AskingFor(slot="delay_origin"))
        self.reply("Where are you currently?")

    @Rule(
        DelayJourney(
            origin=P(lambda x: x is not None),
            destination=None
        ),
        NOT(AskingFor()),
        salience=79
    )
    def ask_delay_destination(self):

        self.declare(AskingFor(slot="delay_destination"))
        self.reply("Where are you travelling to?")

    @Rule(
        DelayJourney(
            origin=P(lambda x: x is not None),
            destination=P(lambda x: x is not None),
            current_delay=P(lambda x: x is not None),
            reason=None
        ),
        NOT(AskingFor()),
        salience=77
    )
    def ask_reason(self):
        self.declare(AskingFor(slot="delay_reason"))
        self.reply("Do you have the delay reason code?")

    @Rule(
        DelayJourney(
            origin=P(lambda x: x is not None),
            destination=P(lambda x: x is not None),
            current_delay=None
        ),
        NOT(AskingFor()),
        salience=78
    )
    def ask_current_delay(self):
        self.declare(AskingFor(slot="delay_minutes"))
        self.reply("How many minutes late is your train currently?")

    @Rule(
        AS.ui << UserInput(text=MATCH.text),
        AS.dj << DelayJourney(),
        NOT(Booking()),
        salience=85
    )
    def extract_delay_entities(self, ui, dj, text):

        updates = {}
        asking = self.current_asking()

        if asking == "delay_origin":
            o, _ = extract_stations(text, "origin")
            if o:
                updates["origin"] = o

        elif asking == "delay_destination":
            _, d = extract_stations(text, "destination")
            if d:
                updates["destination"] = d

        elif asking == "delay_minutes":
            m = re.search(r"\d+", text)
            if m:
                updates["current_delay"] = int(m.group())

        elif asking == "delay_reason":
            no_words = ("no", "none", "dont", "dont", "havent", "n/a")
            m = re.search(r"\d+", text)
            if m:
                updates["reason"] = int(m.group())
            elif any(w in text.lower() for w in no_words):
                updates["reason"] = 0

        if updates:
            self.modify(dj, **updates)
            self.retract_by_type(AskingFor)

        self.retract(ui)

    @Rule(
        DelayJourney(
            origin=P(lambda x: x is not None),
            destination=P(lambda x: x is not None),
            current_delay=P(lambda x: x is not None),
            reason=P(lambda x: x is not None)
        ),

        AS.dj << DelayJourney(
            origin=MATCH.o,
            destination=MATCH.d,
            current_delay=MATCH.cd,
            reason=MATCH.r
        ),

        NOT(DelayPrediction()),
        salience=50
    )
    def run_prediction(self, o, d, cd, r):
        try:
            prediction = predict_delay(
                current_station=o,
                destination=d,
                current_delay=cd,
                reason=r,
                hour=datetime.now().hour,
                day=datetime.now().weekday(),
                routes=ROUTES
            )

            self.declare(
                DelayPrediction(minutes=round(prediction, 1))
            )
        except Exception as e:
            print("Sorry, I don't have the Information on that Journey")
            self.reply("Can I help you with anything else?")
            self.retract_by_type(DelayJourney)
            self.retract_by_type(DelayPrediction)
            self.retract_by_type(AskingFor)

    @Rule(DelayPrediction(minutes=MATCH.m),
        salience=40)
    def respond_prediction(self, m):
        self.reply(f"Your train is predicted to arrive approximately {m} minutes late.")
        if m > 15:
            self.reply("You may be entitled to delay compensation")

        self.reply("Can I help you with anything else?")
        self.retract_by_type(DelayJourney)
        self.retract_by_type(DelayPrediction)
        self.retract_by_type(AskingFor)


    #Final check and summary
    def summary(self, bk):
        lines = [
            f"  From : {bk['origin']}",
            f"  To : {bk['destination']}",
            f"  Date : {bk['date']}",
            f"  Time : {bk['time']}",
            f"  Ticket : {bk['ticket_type']}",
        ]
        if bk["ticket_type"] == "return":
            lines += [
                f"  Return date : {bk['return_date']}",
                f"  Return time : {bk['return_time']}",
            ]
        lines += [
            f"  Adults : {bk['adults']}",
            f"  Children : {bk['children']}",
            f"  Railcard : {bk['railcard'] or 'none'}",
        ]
        return "\n".join(lines)

    @Rule(
        AS.bk << Booking(),
        RailcardAsked(),
        NOT(Booking(origin=None)), NOT(Booking(destination=None)),
        NOT(Booking(date=None)), NOT(Booking(time=None)),
        NOT(Booking(ticket_type=None)),
        NOT(AwaitingConfirm()),
        NOT(AskingFor()),
        NOT(BookingComplete()),
        salience=50
    )
    def request_confirmation(self, bk):
        self.declare(AwaitingConfirm())
        self.reply(
            "Here's what I have:\n" + self.summary(bk) +
            "\n\nShall I search for the cheapest ticket? (yes / no)"
        )


    def search_and_present(self, bk):
        try:
            xml = api.get_journey(
                origin_crs=bk["origin"],
                destination_crs=bk["destination"],
                datetime_str=build_datetime(bk["date"], bk["time"]),
                adults=bk["adults"],
                children=bk["children"],
            )
            journeys = NationalRailAPI.parse_journeys(xml)
        except Exception as e:
            return f"Sorry, I couldn't reach National Rail at the moment: {e}"

        if not journeys:
            return "I couldn't find any trains for that journey. Try a different time or date?"

        def min_price(j):
            fares = [f["price_pence"] for f in j.get("fares", []) if f.get("price_pence")]
            return min(fares) if fares else float("inf")

        def build_journey_url(journey):
            url = r"https://www.nationalrail.co.uk/journey-planner/?"

            dep_date = str(journey.get("departure"))[:10]
            dep_time = str(journey.get("departure"))[11:16]
            dt = datetime.strptime(f"{dep_date} {dep_time}", "%Y-%m-%d %H:%M")

            formatted_date = dt.strftime("%d%m%y")
            hour = dt.strftime("%H")

            # have to search every 15 minutes, not for exact times
            minute = int(dt.strftime("%M"))

            railcard_codes = {
                "16-17": "TSU%7C1",
                "16-25": "YNG%7C1",
                "26-30": "TST%7C1",
                "disabled": "DIS%7C1",
                "family & friends": "FAM%7C1",
                "network": "NEW%7C1",
                "senior": "SRN%7C1",
                "two together": "2TR%7C1",
                "veterans": "VET%7C1"
            }

            ticket_type = bk["ticket_type"]
            # single
            if bk['ticket_type'] == "one way":
                url += (f""
                        f"type=single&"
                        f"origin={bk['origin']}&"
                        f"destination={bk['destination']}&"
                        f"leavingType=departing&"
                        f"leavingDate={formatted_date}&"
                        f"leavingHour={hour}&"
                        f"leavingMin={(int(minute) // 15) * 15:02d}&"
                        f"adults=1&"
                        f"children=0&")

                if bk['railcard']:
                    url += (f"railcards={railcard_codes[bk['railcard']]}&")

                url += (f"extraTime=0#O")


            # return
            elif bk['ticket_type'] == "return":
                # TICKET TYPE NEEDS FIXING - API currently does not return correct return details in journeys
                # however the hyperlinks work

                return_date = "310526"
                return_hour = "12"
                return_min = "00"

                # returnType=departing&returnDate=270526&returnHour=18&returnMin=15&
                url += (f""
                        f"type=return&"
                        f"origin={bk['origin']}&"
                        f"destination={bk['destination']}&"
                        f"leavingType=departing&"
                        f"leavingDate={formatted_date}&"
                        f"leavingHour={hour}&"
                        f"leavingMin={(int(minute) // 15) * 15:02d}&"
                        f"returnType=departing&"
                        f"returnDate={return_date}"
                        f"returnHour={return_hour}&"
                        f"returnHour={return_min}&"
                        f"adults=1&"
                        f"children=0&")

                if bk['railcard']:
                    url += (f"railcards={railcard_codes[bk['railcard']]}&")

                url += (f"extraTime=0#O")

            # open return
            elif bk['ticket_type'] == "open return":
                # TICKET TYPE NEEDS FIXING - API currently does not return correct open return details in journeys
                # however the hyperlinks work
                url += (f""
                        f"type=open&"
                        f"origin={bk['origin']}&"
                        f"destination={bk['destination']}&"
                        f"leavingType=departing&"
                        f"leavingDate={formatted_date}&"
                        f"leavingHour={hour}&"
                        f"leavingMin={(int(minute) // 15) * 15:02d}&"
                        f"adults=1&"
                        f"children=0&")

                if bk['railcard']:
                    url += (f"railcards={railcard_codes[bk['railcard']]}&")

                url += (f"extraTime=0#O")

            return url

        journeys.sort(key=min_price)

        formatted_journeys = []
        formatted_journeys.append({
            "msg": "Here are the available trains:\n"
        })

        for i, j in enumerate(journeys[:3], 1):
            dep = j.get("departure", "?")[11:16]
            arr = j.get("arrival", "?")[11:16]
            c = j.get("changes", 0)
            cs = "direct" if c == 0 else f"{c} change{'s' if c > 1 else ''}"
            p = min_price(j)
            p = p * (1 - get_discount(bk['railcard']))

            ps = f"£{p / 100:.2f}" if p != float("inf") else "N/A"
            text = (f" {i}. Depart {dep}  ->  Arrive {arr}  ({cs})  from {ps}")

            url = build_journey_url(j)
            formatted_journeys.append({
                "text": text,
                "url": url
            })

        p0 = min_price(journeys[0])
        if p0 != float("inf"):
            formatted_journeys.append({
                "cps": f"\nCheapest: {journeys[0].get('departure', '?')[11:16]} at £{p0 / 100:.2f}"
            })
        return formatted_journeys

    @Rule(
        AS.ui << UserInput(text=MATCH.text),
        AS.bk << Booking(),
        AwaitingConfirm(),
        salience=100
    )
    def handle_confirmation(self, ui, bk, text):
        self.retract(ui)
        self.retract_by_type(AwaitingConfirm)

        if any(w in text.lower() for w in ("yes", "yeah", "sure", "ok", "confirm")):
            result = self.search_and_present(bk)
            self.reply(result)
            self.reply("Can I help you with anything else?")
            self.retract_by_type(Booking)
            self.retract_by_type(BookingComplete)
            self.retract_by_type(RailcardAsked)
            self.retract_by_type(AskingFor)
            self.retract_by_type(AwaitingConfirm)
        else:
            self.retract(bk)
            self.retract_by_type(RailcardAsked)
            self.declare(Booking())
            self.reply("No problem, let's start over. Where would you like to travel from?")



# start engine for GUI
engine = BookingEngine()
engine.reset()

def get_startup_msg():
    engine._replies = []
    engine.declare(Intent(value="greeting"))
    engine.run()

    return engine._replies.copy()

def get_response(user_input):
    engine._replies = []

    try:
        intent = intention_by_keyword(user_input)

    except KeyError:
        intent = None

    if intent:
        engine.declare(Intent(value=intent))

    engine.declare(UserInput(text=user_input))

    engine.run()

    replies = engine._replies.copy()

    return replies



if __name__ == "__main__":
    engine = BookingEngine()
    engine.reset()
    engine._replies = []

    engine.declare(Intent(value="greeting"))
    engine.run()
    for r in engine._replies:
        print(f"BOT: {r}")

    while True:
        try:
            user_input = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("BOT: Goodbye!")
            break

        if not user_input:
            continue

        engine._replies = []

        #detect intent, then assert facts for this turn
        try:
            intent = intention_by_keyword(user_input)
        except KeyError:
            intent = None

        if not intent:
            # No recognised intent — still assert UserInput so entity extraction can run
            engine.declare(UserInput(text=user_input))
            engine.run()
            for r in engine._replies:
                if r:
                    print(f"BOT: {r}")
            continue

        engine.declare(Intent(value=intent))
        engine.declare(UserInput(text=user_input))
        engine.run()

        for r in engine._replies:
            if r:
                print(f"BOT: {r}")

        if any(isinstance(f, SessionDone) for f in engine.facts.values()):
            print("BOT: Goodbye!")
            break

