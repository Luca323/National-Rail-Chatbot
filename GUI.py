import webbrowser
from tkinter import *
from datetime import datetime
from experta_re import get_startup_msg, get_response
from database import list_conversations, get_conversation


def show_history():
    win = Toplevel()
    win.title("Conversation History")
    win.geometry("900x500")
    win.configure(bg="#edd080")

    # left: list of past conversations
    left = Frame(win, bg="#edd080")
    left.pack(side=LEFT, fill=Y, padx=10, pady=10)

    Label(left, text="Past conversations", bg="#edd080", font=("Arial", 10, "bold")).pack(anchor=W)

    list_wrap = Frame(left)
    list_wrap.pack(fill=Y, expand=True)

    listbox = Listbox(list_wrap, width=45, height=25, font=("Arial", 9))
    listbox.pack(side=LEFT, fill=Y)

    lb_scroll = Scrollbar(list_wrap, command=listbox.yview)
    lb_scroll.pack(side=RIGHT, fill=Y)
    listbox.config(yscrollcommand=lb_scroll.set)

    # right: messages from the selected conversation
    right = Frame(win, bg="#edd080")
    right.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)

    Label(right, text="Messages", bg="#edd080", font=("Arial", 10, "bold")).pack(anchor=W)

    msg_wrap = Frame(right)
    msg_wrap.pack(fill=BOTH, expand=True)

    msg_box = Text(msg_wrap, wrap=WORD, bg="white", fg="black",
                   font=("Arial", 10), padx=8, pady=8, bd=0)
    msg_box.pack(side=LEFT, fill=BOTH, expand=True)
    msg_box.tag_config("user", foreground="#1565C0")
    msg_box.tag_config("bot", foreground="#2E7D32")
    msg_box.config(state="disabled")

    msg_scroll = Scrollbar(msg_wrap, command=msg_box.yview)
    msg_scroll.pack(side=RIGHT, fill=Y)
    msg_box.config(yscrollcommand=msg_scroll.set)

    # populate the conversation list
    try:
        conversations = list_conversations()
    except Exception as ex:
        Label(left, text=f"DB error: {ex}", fg="red", wraplength=300, bg="#edd080").pack()
        return

    conv_ids = []
    for conv_id, started_at, preview in conversations:
        ts = started_at.strftime("%Y-%m-%d %H:%M") if started_at else "?"
        if preview:
            preview_text = preview[:40] + ("..." if len(preview) > 40 else "")
        else:
            preview_text = "(no user messages)"
        listbox.insert(END, f"#{conv_id}  {ts}  - {preview_text}")
        conv_ids.append(conv_id)

    def on_select(event):
        sel = listbox.curselection()
        if not sel:
            return
        conv_id = conv_ids[sel[0]]

        msg_box.config(state="normal")
        msg_box.delete("1.0", END)

        try:
            rows = get_conversation(conv_id)
        except Exception as ex:
            msg_box.insert(END, f"DB error: {ex}", "bot")
            msg_box.config(state="disabled")
            return

        for sender, text, created_at in rows:
            ts = created_at.strftime("%H:%M:%S") if created_at else ""
            tag = "user" if sender == "user" else "bot"
            label = "You" if sender == "user" else "Bot"
            msg_box.insert(END, f"[{ts}] {label} -> {text}\n\n", tag)

        msg_box.config(state="disabled")

    listbox.bind("<<ListboxSelect>>", on_select)


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
    user_text = e.get().strip()
    if not user_text:
        return

    txt.config(state="normal")
    current_time = datetime.now().strftime("%H:%M:%S")

    user_msg = f"[{current_time}] You -> {user_text}"
    txt.insert(END, "\n" + user_msg, "user")

    # loading indicator while the (potentially slow) API call runs
    loading_pos = txt.index("end-1c")
    txt.insert(END, "\n\n    Searching...", "loading")
    txt.see(END)
    txt.config(state="disabled")
    txt.update_idletasks()  # force GUI repaint before blocking call

    responses = get_response(user_text)

    txt.config(state="normal")
    txt.delete(loading_pos, "end-1c")

    print(responses)

    for response in responses:
        if isinstance(response, str):
            bot_msg = f"[{current_time}] Bot -> {response}"
            txt.insert(END, "\n\n" + bot_msg + "\n", "bot")

        # for journey hyperlinks
        elif isinstance(response, list):
            for link in response:
                if "url" in link:
                    add_hyperlink(txt, link["text"] + "\n", link["url"])
                else:
                    if "cps" in link:
                        txt.insert(END, "\n" + link["cps"], "bot")
                    else:
                        bot_msg = f"[{current_time}] Bot -> {link['msg']}"
                        txt.insert(END, "\n\n" + bot_msg + "\n", "bot")

            txt.insert(END, "\n")

    txt.see(END) # auto-scroll to newest message
    e.delete(0, END) # clear entry field
    txt.config(state="disabled")


def new_disp():
    window = Tk()
    window.title("National Rail Chatbot")
    window.geometry("800x600")
    window.configure(bg="#edd080")

    # header (centred title with history button on the right)
    header = Frame(window, bg="black")
    header.pack(fill=X)
    # three equal columns so the title in the middle stays truly centred
    header.grid_columnconfigure(0, weight=1, uniform="hdr")
    header.grid_columnconfigure(1, weight=1, uniform="hdr")
    header.grid_columnconfigure(2, weight=1, uniform="hdr")

    title = Label(header, text="National Rail Chatbot", bg="black", fg="white",
                  font=("Arial", 11, "bold"), pady=12)
    title.grid(row=0, column=1)

    history_btn = Button(header, text="History", command=show_history,
                         bg="#77bff2", fg="black", activebackground="#a8d4f5",
                         activeforeground="black", relief="raised", bd=1,
                         padx=12, pady=2)
    history_btn.grid(row=0, column=2, sticky="e", padx=12, pady=8)

    # chat frame
    chat_frame = Frame(window, bg="#77bff2", padx=20, pady=15)
    chat_frame.pack(fill=BOTH, expand=True)

    # outer border
    border_frame = Frame(chat_frame, bg="black", bd=2, relief="solid")
    border_frame.pack(fill=BOTH, expand=True)

    # chat box
    chat_box = Text(border_frame, wrap=WORD, bg="white", fg="black", font=("Arial", 10), padx=10, pady=10, bd=0)
    chat_box.pack(side=LEFT, fill=BOTH, expand=True)

    # colour-coded message tags so user/bot distinguishable
    chat_box.tag_config("user", foreground="#1565C0")
    chat_box.tag_config("bot", foreground="#2E7D32")
    chat_box.tag_config("loading", foreground="#888888", font=("Arial", 10, "italic"))

    chat_box.config(state="disabled")

    # initialise startup message
    start_msg = get_startup_msg()
    for msg in start_msg:
        current_time = datetime.now().strftime("%H:%M:%S")
        bot_msg = f"[{current_time}] RailBot -> {msg}"
        chat_box.config(state="normal")
        chat_box.insert(END, "\n" + bot_msg + "\n", "bot")
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