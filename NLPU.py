import difflib
import json
import random
import pandas as pd
from nltk import ngrams
import re
from datetime import datetime, timedelta
import spacy
import spacy.cli

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
    # returns a type of intention if keyword appears in sentence
    with open("intentions.json") as f:
        # load the JSON data into a Python dictionary
        intentions = json.load(f)

    for word in lem_and_clean(sentence).split():
        print(word)

        for type_of_intention in intentions:
            if word in intentions[type_of_intention]["patterns"]:
                print("BOT: " + random.choice(intentions[type_of_intention]["responses"]))
                # Do not change these lines
                # if type_of_intention == 'greeting' and final_chatbot:
                #     print("BOT: We can talk about the time, date, and train tickets.\n(Hint: What time is it?)")
                return type_of_intention
    return None
    # e.g. add ticket type synonyms to intentions


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
station_names = stations_df['NAME'].str.lower().tolist() # get list of stations from df

def get_station(userInput):
    # returns the best match station from a uncleaned sentence
    best_match = None
    best_score = 0

    # look for exact match
    for station in station_names:
        if station in userInput.lower():
            best_match = station

    # if no exact match, look for closest matches using n-grams
    if best_match == None:
        for i in range(1,4): # unigrams, bigrams & trigrams
            ngram = ngrams(userInput.split(), n=i)
            for grams in ngram:
                gram = ' '.join(grams)
                close_matches = difflib.get_close_matches(gram, station_names, n=1, cutoff=0.7)

                if close_matches:
                    score = difflib.SequenceMatcher(None, gram, close_matches[0]).ratio()

                    if score > best_score:
                        best_match = close_matches[0]
                        best_score = score


    print(f"Best match: {best_match}")
    print(f"Best score: {best_score}")

    station_code = stations_df['CRS'].loc[stations_df['NAME'] == best_match.upper()].values[0]
    print(f"Station code: {station_code}")
    return station_code

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
    "16-17 saver": "16-17",
    "16-25 railcard": "16-25",
    "26-30 railcard": "26-30",
    "disabled persons railcard": "disabled",
    "family & friends railcard": "f&f",
    "network railcard": "network",
    "senior railcard": "senior",
    "two together railcard": "2together",
    "veterans railcard": "veteran"
}

def railcard_choice(userInput):
    # get the railcard from an uncleaned user input
    doc = nlp(userInput.lower())

    for card in railcards.keys():
        for token in doc:
            # ignore stop words and word == "railcard", look for token in railcard keys (types)
            if not token.is_stop and token.text != "railcard" and token.text in card:
                print(f"Railcard type: {card}, Code: {railcards[card]}")
                return railcards[card]

    return None

def check_ticket(userInput):
    userInput =userInput.lower()

    ticket_types = ["one way", "return", "open return", "open ticket"]

    for ticket in ticket_types:
        if ticket in userInput:
            print(f"Ticket type: {ticket}")
            return ticket

    return None

"""
 NOTES
prep sentences for nlp ->lem and clean text

check intention by keyword
-> create an intentions json for typical patterns+responses

compare user sentence to premade sentences to generate a response by similarity of text

get info for travelling date and time, departure station, destination station, single or return etc.

ticket details needed:
- origin station -> 
- destination station -> 
- date -> ner
- time -> ner
- ticket type (single, return, open-return, etc) -> nlp
- no of tickets (e.g. adult, children) ->
- railcard -> 
"""

if __name__ == "__main__":

    sentences = ["Hello, I would like to book a train ticket to Norwich!",
                 "Hey, I want to travel to York next friday!",
                 "Thank you for helping me book my single ticket to west ham.",
                 "I want a return ticket to London Liverpool Street on Tuesday",
                 "I want to book a train for Monday 20th April at 14:00 to travel to Selhurst.",
                 "I want to travel to Portsmouth and Southsea on 30th April.",
                 "I want to travel to Portsmouth Harbour with a 16-25. railcard.",
                 "I want to travel to Bristol Temple Meads with a Veterans railcard.",
                 "I want to travel to Victoria London with a senior railcard."]


    for s in sentences:
        print(f"\nSentence: {s}\nCleaned text: {lem_and_clean(s)}")
        extract_time_date(lem_and_clean(s))
        get_station(s)
        check_ticket(s)
        railcard_choice(s)

        # intention_by_keyword(s)



