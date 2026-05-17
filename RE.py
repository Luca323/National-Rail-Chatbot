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

"""
functions to get the information that might be presented in the chatbot. Uses some of the NLPU functions but also has
fallbacks on regex to get the information out


Flow:
1. Detect intent
2. Extract entities
3. Fill missing slots
4. Ask user for missing info
5. Confirm
6. Call API
"""

api = NationalRailAPI()
#llm = LlamaWrapper()
ROUTES = extract_routes(pd.read_csv('dataset.csv')['location']) #For later use by the prediction model, call here to save at runtime



#state of booking holding information. Essentially a data container to hold every piece of info collected

class BookingState:
    def __init__(self):
        self.origin = None
        self.destination = None
        self.date = None
        self.time = None
        self.ticket_type = None
        self.return_date = None
        self.return_time = None
        self.adults = 1
        self.children = 0
        self.railcard = None
        self.railcard_asked = False

    def missing(self):
        slots = {
            "origin": self.origin,
            "destination": self.destination,
            "date": self.date,
            "time": self.time,
            "ticket_type": self.ticket_type,
        }
        if self.ticket_type == "return":
            slots["return_date"] = self.return_date
            slots["return_time"] = self.return_time
        return [k for k, v in slots.items() if v is None]

    def is_complete(self):
        return len(self.missing()) == 0 and self.railcard_asked

    def summary(self):
        lines = [
            f"  From        : {self.origin}",
            f"  To          : {self.destination}",
            f"  Date        : {self.date}",
            f"  Time        : {self.time}",
            f"  Ticket      : {self.ticket_type}",
        ]
        if self.ticket_type == "return":
            lines += [
                f"  Return date : {self.return_date}",
                f"  Return time : {self.return_time}",
            ]
        lines += [
            f"  Adults      : {self.adults}",
            f"  Children    : {self.children}",
            f"  Railcard    : {self.railcard or 'none'}",
        ]
        return "\n".join(lines)


SLOT_PROMPTS = {
    "origin": "Where would you like to travel from?",
    "destination": "Where would you like to travel to?",
    "date": "What date would you like to travel?",
    "time": "What time would you like to depart?",
    "ticket_type": "Would you like a one-way, return, or open return ticket?",
    "return_date": "What date would you like to return?",
    "return_time": "What time would you like to return?",
}

RAILCARD_PROMPT = (
    "Do you have a railcard? "
    "(16-17, 16-25, 26-30, disabled, family & friends, network, senior, "
    "two together, veterans — or 'no')"
)


#This is the reasoning engine that manages the conversation
class ReasoningEngine:
    def __init__(self):
        self.state = BookingState()
        self.booking_active = False
        self.awaiting_confirm = False
        self.awaiting_railcard = False
        self.done = False
        self._last_asked = None

#This gets called on messages to extract what the user wants from the bot
    def _extract_all(self, text):
        spacy_dates, spacy_times = extract_time_date(text)

        parsed_date = None
        for d in spacy_dates:
            parsed_date = parse_date(d)
            if parsed_date:
                break
        if not parsed_date:
            parsed_date = parse_date(text)

        if self.state.ticket_type == "return" and not parsed_date:
            if "same day" in text.lower():
                parsed_date = self.state.date

        parsed_time = None
        for t in spacy_times:
            parsed_time = parse_time(t)
            if parsed_time:
                break
        if not parsed_time:
            parsed_time = parse_time(text)

        is_return_context = (
                self.state.ticket_type == "return"
                and self.state.date
                and self._last_asked in ("return_date", "return_time")
        )

        if is_return_context:
            if parsed_date and not self.state.return_date:
                self.state.return_date = parsed_date
            if parsed_time and not self.state.return_time:
                self.state.return_time = parsed_time
        else:
            if parsed_date and not self.state.date:
                self.state.date = parsed_date
            if parsed_time and not self.state.time:
                self.state.time = parsed_time
            # If both times present in one message (outbound + return), grab second for return
            if self.state.ticket_type == "return" and self.state.time:
                all_times = [parse_time(t) for t in spacy_times if parse_time(t)]
                if not all_times:
                    # try regex on whole text for multiple times
                    all_times = re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", text, re.I)
                    all_times = [parse_time(t) for t in all_times if parse_time(t)]
                if len(all_times) >= 2 and not self.state.return_time:
                    self.state.return_time = all_times[1]

        #stations
        if not self.state.origin or not self.state.destination:
            origin_crs, dest_crs = extract_stations(text, self._last_asked)
            if origin_crs and not self.state.origin:
                self.state.origin = origin_crs
            if dest_crs and not self.state.destination:
                self.state.destination = dest_crs

        #type of ticket
        if not self.state.ticket_type:
            self.state.ticket_type = check_ticket(text)

        #number of passengers
        adult_match = re.search(r"(\d+)\s+adult", text, re.I)
        child_match = re.search(r"(\d+)\s+child", text, re.I)
        if adult_match: self.state.adults = int(adult_match.group(1))
        if child_match:  self.state.children = int(child_match.group(1))

    def process(self, user_input):

        try:
            intent = intention_by_keyword(user_input)
        except KeyError as e:
            return "Sorry, I didn’t quite understand that. Could you rephrase your request?", False

        if intent == "goodbye":
            return "", True
        if intent in ("greeting", "thanks"):
            return "", False

        if self.done:
            if intent == "book":
                self._reset()
            else:
                return "Say 'book' to search again or 'goodbye' to leave.", False

        self._extract_all(user_input)

        if not self.booking_active:
            if intent == "book" or self.state.origin or self.state.destination:
                self.booking_active = True
            else:
                return "I can help you find the cheapest train ticket. Just say 'I'd like to book a ticket'.", False

        missing = self.state.missing()
        if missing:
            next_slot = missing[0]
            #NLPU book intent already printed "where do you want to travel from?"
            if intent == "book" and next_slot == "origin" and not self._last_asked:
                self._last_asked = "origin"
                return "", False
            self._last_asked = next_slot
            return SLOT_PROMPTS[next_slot], False

        if not self.state.railcard_asked:
            self.awaiting_railcard = True
            self._last_asked = "railcard"
            return RAILCARD_PROMPT, False

        self.awaiting_confirm = True
        return (
                "Here's what I have:\n"
                + self.state.summary()
                + "\n\nShall I search for the cheapest ticket? (yes / no)"
        ), False

    def handle_railcard(self, user_input):
        self.awaiting_railcard = False
        self.state.railcard_asked = True
        self._last_asked = None

        if any(w in user_input.lower() for w in ("no", "none", "don't", "dont", "haven't", "havent", "n/a")):
            self.state.railcard = None
        else:
            self.state.railcard = railcard_choice(user_input)

        self.awaiting_confirm = True
        return (
                "Here's what I have:\n"
                + self.state.summary()
                + "\n\nShall I search for the cheapest ticket? (yes / no)"
        ), False

    def confirm(self, user_input):
        self.awaiting_confirm = False

        if any(w in user_input.lower() for w in ("yes", "yeah", "sure", "ok", "confirm")):
            result = search_and_present(self.state)
            self.done = True
            return result + "\n\nSay 'book' to search again or 'goodbye' to leave.", False

        self._reset()
        return "No problem, let's start over. Where would you like to travel from?", False

    def _reset(self):
        self.state = BookingState()
        self.booking_active = False
        self.awaiting_confirm = False
        self.awaiting_railcard = False
        self.done = False
        self._last_asked = None

#this calls the API to look for the ticket and sorts the journeys by price and displays the best ones

def search_and_present(state):
    try:
        xml = api.get_journey(
            origin_crs=state.origin,
            destination_crs=state.destination,
            datetime_str=build_datetime(state.date, state.time),
            adults=state.adults,
            children=state.children,
        )
        journeys = NationalRailAPI.parse_journeys(xml)
    except Exception as e:
        return f"Sorry, I couldn't reach National Rail at the moment: {e}"

    if not journeys:
        return "I couldn't find any trains for that journey. Would you like to try a different time or date?"

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
        lines.append(f"  {i}. Depart {dep}  →  Arrive {arr}  ({cs})  from {ps}")

    p0 = min_price(journeys[0])
    if p0 != float("inf"):
        lines.append(f"\nCheapest: {journeys[0].get('departure', '?')[11:16]} departure at £{p0 / 100:.2f}")

    return "\n".join(lines)

if __name__ == "__main__":
    engine = ReasoningEngine()
    print("BOT: Hello! I can help you find the cheapest train ticket. Where would you like to travel?")

    while True:
        try:
            user_input = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("BOT: Goodbye!")
            break

        if not user_input:
            continue

        if engine.awaiting_confirm:
            reply, should_exit = engine.confirm(user_input)
        elif engine.awaiting_railcard:
            reply, should_exit = engine.handle_railcard(user_input)
        else:
            reply, should_exit = engine.process(user_input)

        if reply:
            print(f"BOT: {reply}")

        if should_exit:
            break

"""
This extracts the booking information and holds the flow of the conversation when ran. The outputs right now are 
kept for debugging to see what the class is currently holding. Once information is submitted it then checks and searches
for tickets.
"""