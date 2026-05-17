from API import NationalRailAPI, LlamaWrapper
from NLPU import (intention_by_keyword, extract_time_date, extract_stations,
                  check_ticket, railcard_choice, re,
                  parse_time, parse_date, build_datetime)
from PredictionModel import extract_routes, pd, predict_delay
import collections
import collections.abc
for type_name in ['Mapping','MutableMapping','Iterable','MutableSet']:
    if not hasattr(collections, type_name):
        setattr(collections, type_name, getattr(collections.abc, type_name))

from experta import *

api = NationalRailAPI()

SLOT_PROMPTS = {
    "origin":       "Where would you like to travel from?",
    "destination":  "Where would you like to travel to?",
    "date":         "What date would you like to travel?",
    "time":         "What time would you like to depart?",
    "ticket_type":  "Would you like a one-way, return, or open return ticket?",
    "return_date":  "What date would you like to return?",
    "return_time":  "What time would you like to return?",
}

RAILCARD_PROMPT = (
    "Do you have a railcard? "
    "(16-17, 16-25, 26-30, disabled, family & friends, network, senior, "
    "two together, veterans — or 'no')"
)

# -----------------------------
# FACT DEFINITION
# -----------------------------
class UserInput(Fact):
    text = Field(str, mandatory=True)

class Intent(Fact):
    value = Field(str, mandatory=True)

class Booking(Fact):
    origin       = Field(str,  default=None)
    destination  = Field(str,  default=None)
    date         = Field(str,  default=None)
    time         = Field(str,  default=None)
    ticket_type  = Field(str,  default=None)
    return_date  = Field(str,  default=None)
    return_time  = Field(str,  default=None)
    adults       = Field(int,  default=1)
    children     = Field(int,  default=0)
    railcard     = Field(object,  default=None)

class AskingFor(Fact):
    slot = Field(str, mandatory=True)

class RailcardAsked(Fact):  pass
class AwaitingConfirm(Fact): pass
class BookingComplete(Fact): pass
class SessionDone(Fact):     pass


class BookingEngine(KnowledgeEngine):

    @Rule(Intent(value='greeting'), salience=100)
    def handle_greeting(self):
        self.reply("Hello! I can help you find the cheapest train ticket. "
                    "Where would you like to travel?")
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

    @Rule(Intent(value="book"), NOT(Booking()), salience=90)
    def start_booking(self):
        self.declare(Booking())
        self.retract_by_type(Intent)

    @Rule(UserInput(), NOT(Booking()), NOT(Intent(value="goodbye")), salience=95)
    def auto_start_booking(self):
        self.declare(Booking())

    @Rule(
        AS.ui << UserInput(text=MATCH.text), AS.bk << Booking(),
        salience=80
    )
    def extract_entities(self, ui, bk, text):
        updates = {}

        #Dates and time
        spacy_dates, spacy_times = extract_time_date(text)
        parsed_date = next((parse_date(d) for d in spacy_dates if parse_date(d)), None)
        if not parsed_date:
            parsed_date = parse_date(text)

        parsed_time = next((parse_time(t) for t in spacy_times if parse_time(t)), None)
        if not parsed_time:
            parsed_time = parse_time(text)

        asking = self.current_asking()

        is_return_context = (
                bk["ticket_type"] == "return"
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

            #double check
            if bk["ticket_type"] == "return" and (bk["time"] or updates.get("time")):
                all_times = [parse_time(t) for t in spacy_times if parse_time(t)]
                if len(all_times) >= 2 and not bk["return_time"]:
                    updates["return_time"] = all_times[1]

        #Stations
        if not bk["origin"] or not bk["destination"]:
            o_crs, d_crs = extract_stations(text, asking)
            if o_crs and not bk["origin"]:
                updates["origin"] = o_crs
            if d_crs and not bk["destination"]:
                updates["destination"] = d_crs

        #ticket type
        if not bk["ticket_type"]:
            tt = check_ticket(text)
            if tt:
                updates["ticket_type"] = tt

        #passengers
        am = re.search(r"(\d+)\s+adult", text, re.I)
        cm = re.search(r"(\d+)\s+child", text, re.I)
        if am:
            updates["adults"] = int(am.group(1))
        if cm:
            updates["children"] = int(cm.group(1))

        if updates:
            self.modify(bk, **updates)
            self.retract_by_type(AskingFor)  # <-- add this

        self.retract(ui)


    def current_asking(self):
        for fact in self.facts.values():
            if isinstance(fact, AskingFor):
                return fact["slot"]
        return None

    def reply(self, msg):
        self._replies.append(msg)

    def retract_by_type(self, fact_class):
        for fid, fact in list(self.facts.items()):
            if isinstance(fact, fact_class):
                self.retract(fact)

    def ask_slot(self, slot):
        if self.current_asking() != slot:
            self.retract_by_type(AskingFor)
            self.declare(AskingFor(slot=slot))
            self.reply(SLOT_PROMPTS[slot])

    @Rule(Booking(origin=None), NOT(AskingFor()), NOT(AwaitingConfirm()),salience = 70)
    def ask_origin(self):
        self.ask_slot(slot='origin')

    @Rule(Booking(destination=None), NOT(Booking(origin=None)),
          NOT(AskingFor()), NOT(AwaitingConfirm()), salience=69)
    def ask_destination(self):
        self.ask_slot(slot='destination')

    @Rule(Booking(ticket_type=None), NOT(Booking(origin=None)), NOT(Booking(destination=None)),
          NOT(AskingFor()), NOT(AwaitingConfirm()), salience=68)
    def ask_ticket_type(self):
        self.ask_slot(slot="ticket_type")

    @Rule(Booking(date=None), NOT(Booking(ticket_type=None)),
          NOT(AskingFor()), NOT(AwaitingConfirm()), salience=67)
    def ask_date(self):
        self.ask_slot(slot="date")

    @Rule(Booking(time=None), NOT(Booking(date=None)),
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
        salience=85  # above extract_entities so railcard text isn't also entity-parsed
    )
    def handle_railcard_answer(self, ui, bk, text):
        no_words = ("no", "none", "don't", "dont", "haven't", "havent", "n/a")
        railcard = None if any(w in text.lower() for w in no_words) else railcard_choice(text)
        self.modify(bk, railcard=railcard)
        self.retract(ui)
        self.retract_by_type(AskingFor)

    #Final check and summary
    @staticmethod
    def summary(bk):
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

    @Rule(
        AS.ui << UserInput(text=MATCH.text),
        AS.bk << Booking(),
        AwaitingConfirm(),
        salience=90
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

        journeys.sort(key=min_price)
        lines = ["Here are the available trains:\n"]
        for i, j in enumerate(journeys[:3], 1):
            dep = j.get("departure", "?")[11:16]
            arr = j.get("arrival", "?")[11:16]
            c = j.get("changes", 0)
            cs = "direct" if c == 0 else f"{c} change{'s' if c > 1 else ''}"
            p = min_price(j)
            ps = f"£{p / 100:.2f}" if p != float("inf") else "N/A"
            lines.append(f"  {i}. Depart {dep}  ->  Arrive {arr}  ({cs})  from {ps}")

        p0 = min_price(journeys[0])
        if p0 != float("inf"):
            lines.append(f"\nCheapest: {journeys[0].get('departure', '?')[11:16]} at £{p0 / 100:.2f}")
        return "\n".join(lines)

    @Rule(
        AS.ui << UserInput(text=MATCH.text),
        AS.bk << Booking(),
        AwaitingConfirm(),
        salience=90
    )
    def handle_confirmation(self, ui, bk, text):
        self.retract(ui)
        self.retract_by_type(AwaitingConfirm)

        if any(w in text.lower() for w in ("yes", "yeah", "sure", "ok", "confirm")):
            result = self.search_and_present(bk)
            self.reply(result + "\n\nSay 'book' to search again or 'goodbye' to leave.")
            self.declare(BookingComplete())
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

    # Seed the greeting
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

        # Detect intent, then assert facts for this turn
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

        # THIS BLOCK IS MISSING — add it:
        for r in engine._replies:
            if r:
                print(f"BOT: {r}")

        if any(isinstance(f, SessionDone) for f in engine.facts.values()):
            print("BOT: Goodbye!")
            break

