import difflib
import json
import random
import pandas as pd
from nltk import ngrams
import re
from datetime import datetime, timedelta
import spacy
import spacy.cli
from spacy.matcher import PhraseMatcher

# spacy.cli.download("en_core_web_sm")
nlp = spacy.load('en_core_web_sm')

MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]

def lem_and_clean(text):
    # lemmatize and clean a piece of text
    doc = nlp(text.lower())

    out = ""

    # only accept token if not stop word or punctuation
    for token in doc:
        if not token.is_stop and not token.is_punct:

            out = out + token.lemma_ + " "

    return out.strip() # remove spaces at beginning/end

def intention_by_keyword(sentence):
    with open("intentions.json") as f:
        intentions = json.load(f)
    for word in lem_and_clean(sentence).split():
        for type_of_intention in intentions:
            if word in intentions[type_of_intention]["patterns"]:
                return type_of_intention  # remove the print line
    return None


def extract_time_date(sentence):
    # extract the time and date from a cleaned sentence
    doc = nlp(sentence)

    dates = []
    times = []

    for ent in doc.ents:
        if ent.label_ == "DATE":
            dates.append(ent.text)
        if ent.label_ == "TIME":
            times.append(ent.text)

    print(f"Dates: {dates}")
    print(f"Times: {times}")

    return dates, times


stations_df = pd.read_csv("StationNameAndCode.csv")

def normalise_station(text):
    return (
        text.lower()
        .replace("&", "and")
        .replace("-", " ")
        .replace(".", " ")
        .replace(",", " ")
        .replace("station", " ")
        .strip()
    )

stations_df['NORM'] = stations_df['NAME'].apply(normalise_station)

def score_station(input_text, station_name):
    input = normalise_station(input_text)
    station = normalise_station(station_name)

    # exact match
    if input == station:
        return 1000

    input_tokens = set(input.split())
    station_tokens = set(station.split())

    if input_tokens.issubset(station_tokens):
        return 900 + len(input_tokens)

    overlap = len(input_tokens & station_tokens)
    union = len(station_tokens)

    if union == 0:
        return 0

    return (overlap / union) * 600

def get_station(user_input):
    best_crs = None
    best_score = 0

    for _, row in stations_df.iterrows():
        name = row['NORM']
        crs = row['CRS']

        score = score_station(user_input, name)

        if score > best_score:
            best_score = score
            best_crs = crs

    if best_score < 350:
        return None

    print(best_crs)
    return best_crs

def extract_stations(text, last_asked):
    origin_crs, dest_crs = None, None

    match = re.search(
        r'\bfrom\b\s+(.+?)\s+\bto\b\s+(.+?)(?:\s+(?:on|at|tomorrow|next|\d)|$)',
        text, re.I
    )
    if match:
        try:
            origin_crs = get_station(match.group(1).strip())
        except Exception:
            pass
        try:
            dest_crs = get_station(match.group(2).strip())
        except Exception:
            pass
        return origin_crs, dest_crs

    match = re.search(r'\bto\b\s+(.+?)(?:\s+(?:on|at|tomorrow|next|\d)|$)', text, re.I)
    if match:
        try:
            dest_crs = get_station(match.group(1).strip())
        except Exception:
            pass

    match = re.search(r'\bfrom\b\s+(.+?)(?:\s+(?:on|at|tomorrow|next|to|\d)|$)', text, re.I)
    if match:
        try:
            origin_crs = get_station(match.group(1).strip())
        except Exception:
            pass

    if not origin_crs and not dest_crs:
        if last_asked == "origin":
            try:
                origin_crs = get_station(text)
            except Exception:
                pass
        elif last_asked == "destination":
            try:
                dest_crs = get_station(text)
            except Exception:
                pass

    if origin_crs == dest_crs:
        dest_crs = None

    return origin_crs, dest_crs


def parse_date(text: str) -> str | None:
    t = text.lower().strip()
    today = datetime.now()

    if "tomorrow" in t:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "today" in t or "same day" in t:
        return today.strftime("%Y-%m-%d")

    for i, name in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
        if name in t:
            days_ahead = (i - today.weekday()) % 7 or 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    match = re.search(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + "|".join(MONTHS) + r")\s*(\d{4})?",
        t, re.I
    )
    if match:
        day, month_str, year = int(match.group(1)), match.group(2), match.group(3)
        month = MONTHS.index(month_str.lower()) + 1
        year = int(year) if year else today.year
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    match = re.search(
        r"(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\s*(\d{4})?",
        t, re.I
    )
    if match:
        month_str, day, year = match.group(1), int(match.group(2)), match.group(3)
        month = MONTHS.index(month_str.lower()) + 1
        year = int(year) if year else today.year
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if match:
        return match.group(0)

    return None


def parse_time(text: str) -> str | None:
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.I)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        meridiem = match.group(3).lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"

    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"

    return None


def build_datetime(date_str: str, time_str: str) -> str:
    time_parsed = parse_time(time_str or "")
    if time_parsed:
        hour, minute = int(time_parsed[:2]), int(time_parsed[3:])
    else:
        hour, minute = 10, 0

    try:
        base = datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        base = datetime.now()

    return base.replace(hour=hour, minute=minute, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")

railcards = {
    "16-17": [
        "16-17 saver",
        "16-17 railcard",
        "16 17 railcard"
    ],

    "16-25": [
        "16-25 railcard",
        "16 25 railcard",
        "young persons railcard"
    ],

    "26-30": [
        "26-30 railcard",
        "26 30 railcard"
    ],

    "disabled": [
        "disabled persons railcard",
        "disabled railcard"
    ],

    "f&f": [
        "family and friends railcard",
        "family & friends railcard"
    ],

    "network": [
        "network railcard"
    ],

    "senior": [
        "senior railcard",
        "senior"
    ],

    "2together": [
        "two together railcard",
        "two together"
    ],

    "veteran": [
        "veterans railcard",
        "veteran railcard"
    ]
}

def normalise_rc_input(text):
    return (text.lower().replace("-", " "))

def railcard_choice(userInput):
    print("RAILCARD INPUT:", userInput)
    text = normalise_rc_input(userInput)

    for code, phrases in railcards.items():
        for phrase in phrases:
            if text in normalise_rc_input(phrase):
                print("CODE: ", code)
                return code
    return None

def check_ticket(userInput):
    userInput =userInput.lower()

    ticket_types = ["open return", "one way", "return"]

    for ticket in ticket_types:
        if ticket in userInput:
            print(f"Ticket type: {ticket}")
            return ticket

    return None


if __name__ == "__main__":

    sentences = ["Hello, I would like to book a train ticket to Norwich!",
                 "Hey, I want to travel to York next friday!",
                 "Thank you for helping me book my single ticket to west ham.",
                 "I want a return ticket to Liverpool Street on Tuesday",
                 "I want to book a train for Monday 20th April at 14:00 to travel to Selhurst.",
                 "I want to travel to Portsmouth and Southsea on 30th April.",
                 "I want to travel to Portsmouth Harbour with a 16-25. railcard.",
                 "I want to travel to Bristol Temple Meads with a Veterans railcard.",
                 "I want to travel to Victoria London with a senior railcard."]


    for s in sentences:
        print(f"\nSentence: {s}\nCleaned text: {lem_and_clean(s)}")
        # extract_time_date(lem_and_clean(s))
        get_station(s)
        # check_ticket(s)
        # railcard_choice(s)

        # intention_by_keyword(s)



