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
    railcard     = Field(str,  default=None)

class AskingFor(Fact):
    slot = Field(str, mandatory=True)

class RailcardAsked(Fact):  pass
class AwaitingConfirm(Fact): pass
class BookingComplete(Fact): pass
class SessionDone(Fact):     pass

# -----------------------------
# EXPERT SYSTEM WITH PRIORITY
# -----------------------------

class BookingEngine(KnowledgeEngine):

    @Rule(Intent(value='greeting'), salience=100)
    def handle_greeting(self):
        self._reply("Hello! I can help you find the cheapest train ticket. "
                    "Where would you like to travel?")
        self.retract_by_type(Intent)

    @Rule(Intent(value="thanks"), salience=100)
    def handle_thanks(self):
        self._reply("You're welcome!")
        self.retract_by_type(Intent)

    @Rule(Intent(value="goodbye"), salience=100)
    def handle_goodbye(self):
        self._reply("")
        self.declare(SessionDone())
        self.retract_by_type(Intent)

    @Rule(Intent(value="book"), NOT(Booking()), salience=90)
    def start_booking(self):
        self.declare(Booking())
        self.retract_by_type(Intent)

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

        asking = self._current_asking()

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

        self.retract(ui)  # consumed

    def current_asking(self):
        for fact in self.facts.values():
            if isinstance(fact, AskingFor):
                return fact["slot"]
        return None

    def ask_slot(self, slot):
        if self.current_asking() != slot:
            self.retract_by_type)AskingFor



# -----------------------------
# USER INPUT
# -----------------------------
def ask_boolean(question):
    return input(question + " (yes/no): ").strip().lower() == "yes"


def ask_choice(question, options):
    value = input(f"{question} {options}: ").strip().lower()
    return value


# -----------------------------
# MAIN PROGRAM
# -----------------------------
if __name__ == "__main__":

    print("\n=== CAR FAULT DIAGNOSTIC SYSTEM (PRIORITY MODE) ===\n")


    battery_voltage = ask_choice("Battery voltage", ["low", "normal"])
    clicking_sound = ask_boolean("Clicking sound when turning key?")
    engine_starts = ask_boolean("Does the engine start?")
    headlights_dim = ask_boolean("Headlights dim while driving?")
    overheating = ask_boolean("Engine overheating?")
    brake_fluid = ask_choice("Brake fluid level", ["low", "normal"])
    brake_noise = ask_choice("Brake noise", ["none", "squealing", "grinding"])



    print("\n--- PRIORITISED DIAGNOSIS ---")
