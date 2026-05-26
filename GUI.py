import webbrowser
from tkinter import *
from datetime import datetime
from experta_re import get_startup_msg, get_response

# def send_message(e, txt):
#     current_time = datetime.now().strftime("%H:%M:%S")
#
#     user_msg = f"[{current_time}] You -> {e.get()}"
#     txt.insert(END, "\n" + user_msg)
#
#     user = e.get().lower()
#
#     # Change these to output whatever is returned by the RE
#     if (user == "hello"):
#         bot_msg = f"[{current_time}] Bot -> Hi there, how can I help?"
#
#     elif (user == "goodbye"):
#         bot_msg = f"[{current_time}] Bot -> Thank you for using this service."
#
#     else:
#         bot_msg = f"[{current_time}] Bot -> I don't understand you."
#
#     txt.insert(END, "\n" + bot_msg + "\n")
#
#     # txt.insert(END, "\n")
#     txt.see(END) # auto-scroll to newest message
#     e.delete(0, END) # clear entry field

def add_hyperlink(txt_widget, text, url):
    start = txt_widget.index("end-1c")
    txt_widget.insert("end", text)
    end = txt_widget.index("end-1c")

    tag = f"link-{start}"
    txt_widget.tag_add(tag, start, end)

    txt_widget.tag_config(tag, foreground="blue", underline=True)

    txt_widget.tag_bind(tag, "<Button-1>", lambda e: webbrowser.open(url))

    txt_widget.tag_bind(
        tag,
        "<Enter>",
        lambda e: txt_widget.config(cursor="hand2")
    )

    txt_widget.tag_bind(
        tag,
        "<Leave>",
        lambda e: txt_widget.config(cursor="")
    )

def build_url(journey):
    # https://www.nationalrail.co.uk/journey-planner/?
    # type=single
    # &origin=NRW
    # &destination=SRA
    # &leavingType=departing
    # &leavingDate=270526
    # &leavingHour=16
    # &leavingMin=00
    # &adults=1&
    # extraTime=0#O
    url = "https://www.nationalrail.co.uk/"

    # single - https://www.nationalrail.co.uk/journey-planner/?type=single&origin=NRW&destination=SRA&leavingType=departing&leavingDate=270526&leavingHour=16&leavingMin=15&adults=1&railcards=TST%7C1&extraTime=0#O
    # return - https://www.nationalrail.co.uk/journey-planner/?type=return&origin=NRW&destination=SRA&leavingType=departing&leavingDate=270526&leavingHour=16&leavingMin=15&returnType=departing&returnDate=270526&returnHour=18&returnMin=15&adults=1&railcards=TST%7C1&extraTime=0#O
    # open return - https://www.nationalrail.co.uk/journey-planner/?type=open&origin=NRW&destination=SRA&leavingType=departing&leavingDate=270526&leavingHour=16&leavingMin=15&adults=1&railcards=TST%7C1&extraTime=0#O

    # need to look at getting ticket type from jounrey, then build url based on what params are needed
    return url


def send_message(e, txt):
    txt.config(state="normal")
    current_time = datetime.now().strftime("%H:%M:%S")

    user_msg = f"[{current_time}] You -> {e.get()}"
    txt.insert(END, "\n" + user_msg)

    responses = get_response(e.get())

    print(responses)

    for response in responses:
        if isinstance(response, str):
            bot_msg = f"[{current_time}] Bot -> {response}."
            txt.insert(END, "\n" + bot_msg + "\n")

        elif isinstance(response, list):
            bot_msg = f"[{current_time}] Bot -> Available Trains:"
            txt.insert(END, "\n" + bot_msg + "\n")
            txt.update_idletasks()

            for i, j in enumerate(response, 1):
                print(f"Jounrye: {j}")

                dep = str(j.get("departure"))[11:16]
                arr = str(j.get("arrival"))[11:16]

                print("Depature:::: " + j.get("departure"))

                changes = j.get("changes", 0)

                fares = [
                    f["price_pence"]
                    for f in j.get("fares", [])
                    if f.get("price_pence")
                ]

                cheapest = (
                    min(fares) / 100
                    if fares else 0
                )

                # url = "https://www.nationalrail.co.uk/"
                url = build_url(j)

                add_hyperlink(
                    txt,
                    f"{i}. Depart {dep} -> Arrive {arr} | "
                    f"{changes} changes | "
                    f"£{cheapest:.2f}\n",
                    url
                )

            txt.insert(END, "\n")

    txt.see(END) # auto-scroll to newest message
    e.delete(0, END) # clear entry field
    txt.config(state="disabled")


def new_disp():
    window = Tk()
    window.title("Train Booking Chatbot")
    window.geometry("800x600")
    window.configure(bg="#edd080")

    # header
    header = Label(window, text="Train Booking Chatbot", bg="black", fg="white", pady=12)
    header.pack(fill=X)

    # chat frame
    chat_frame = Frame(window, bg="#77bff2", padx=20, pady=15)
    chat_frame.pack(fill=BOTH, expand=True)

    # outer border
    border_frame = Frame(chat_frame, bg="black", bd=2, relief="solid")
    border_frame.pack(fill=BOTH, expand=True)

    # chat box
    chat_box = Text(border_frame, wrap=WORD, bg="white", fg="black", font=("Arial", 10), padx=10, pady=10, bd=0)
    chat_box.pack(side=LEFT, fill=BOTH, expand=True)
    chat_box.config(state="disabled")

    # initialise startup message
    start_msg = get_startup_msg()
    for msg in start_msg:
        current_time = datetime.now().strftime("%H:%M:%S")
        bot_msg = f"[{current_time}] Bot -> {msg}."
        chat_box.config(state="normal")
        chat_box.insert(END, "\n" + bot_msg + "\n")
        chat_box.config(state="disabled")

    # scrollbar
    scrollbar = Scrollbar(border_frame, command=chat_box.yview)
    scrollbar.pack(side=RIGHT, fill=Y)
    chat_box.config(yscrollcommand=scrollbar.set)

    # bottom area
    bottom_frame = Frame(window, bg="#77bff2", pady=15)
    bottom_frame.pack(fill=X)

    # entry/input field
    entry = Entry(bottom_frame, bd=3, font=("Arial", 12), relief="sunken")
    entry.pack(side=LEFT, padx=(20,10), fill=X, expand=True, ipady=8)

    # send button
    send_btn = Button(bottom_frame, text="Send", command=lambda: send_message(entry, chat_box), padx=20, pady=5)
    send_btn.pack(side=RIGHT, padx=(0,20))
    entry.bind("<Return>", lambda event: send_message(entry, chat_box)) # bind the enter btn for input send

    window.mainloop()


if __name__ == "__main__":
    print("Displaying GUI...")

    new_disp()