import psycopg2

#edit this to connect to local DB. this assumes empty user, localhost is 5432 and database is named chatbot.
#my password is stan but edit it to whatever yours is.
DB_STRING = "postgresql://postgres:stan@localhost:5432/chatbot"

def test_connection():
    try:
        connection = psycopg2.connect(DB_STRING)
        print("Database connected")
        return connection
    except Exception as error:
        print("Failed to connect")

#connects to database
def get_connection():
    return psycopg2.connect(DB_STRING)

#start conversation
def start_conversation():
    #make a new conversation row and give back its id
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO conversations DEFAULT VALUES RETURNING id;"
    )
    conversation_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    connection.close()
    return conversation_id


def log_message(conversation_id, sender, text):
    #save one message linked to a conversation
    #sender is 'user' or 'bot'. text is forced to a string so replies dont break logging
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO messages (conversation_id, sender, text) "
        "VALUES (%s, %s, %s);",
        (conversation_id, sender, str(text))
    )
    connection.commit()
    cursor.close()
    connection.close()


def get_conversation(conversation_id):
    #grab all messages for one conversation, oldest first
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT sender, text, created_at FROM messages "
        "WHERE conversation_id = %s ORDER BY created_at;",
        (conversation_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    return rows

if __name__ == "__main__":
    print(test_connection())