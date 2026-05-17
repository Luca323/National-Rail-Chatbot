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

def send_message(e, txt):
    current_time = datetime.now().strftime("%H:%M:%S")

    user_msg = f"[{current_time}] You -> {e.get()}"
    txt.insert(END, "\n" + user_msg)

    responses = get_response(e.get())

    for response in responses:
        bot_msg = f"[{current_time}] Bot -> {response}."
        txt.insert(END, "\n" + bot_msg + "\n")

    txt.see(END) # auto-scroll to newest message
    e.delete(0, END) # clear entry field


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

    # initialise startup message
    start_msg = get_startup_msg()
    for msg in start_msg:
        current_time = datetime.now().strftime("%H:%M:%S")
        bot_msg = f"[{current_time}] Bot -> {msg}."
        chat_box.insert(END, "\n" + bot_msg + "\n")

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