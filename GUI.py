import webbrowser
from tkinter import *
from datetime import datetime
from experta_re import get_startup_msg, get_response


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
            txt.insert(END, "\n\n" + bot_msg + "\n")

        # for journey hyperlinks
        elif isinstance(response, list):
            for link in response:
                if "url" in link:
                    add_hyperlink(txt, link["text"] + "\n", link["url"])
                else:
                    if "cps" in link:
                        txt.insert(END, "\n" + link["cps"])
                    else:
                        bot_msg = f"[{current_time}] Bot -> {link['msg']}."
                        txt.insert(END, "\n\n" + bot_msg + "\n")

            txt.insert(END, "\n")

    txt.see(END) # auto-scroll to newest message
    e.delete(0, END) # clear entry field
    txt.config(state="disabled")


def new_disp():
    window = Tk()
    window.title("National Rail Chatbot")
    window.geometry("800x600")
    window.configure(bg="#edd080")

    # header
    header = Label(window, text="National Rail Chatbot", bg="black", fg="white", pady=12)
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
        bot_msg = f"[{current_time}] RailBot -> {msg}."
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