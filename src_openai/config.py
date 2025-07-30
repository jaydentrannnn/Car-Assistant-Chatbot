import os
import gradio as gr
from rich.theme import Theme
import getpass

#SQLDATABASE
TABLE_DEFINITION = """
create table cars2025
(
    "Company Names"             TEXT,
    "Cars Names"                TEXT,
    Engines                     TEXT,
    "CC/Battery Capacity"       REAL,
    HorsePower                  REAL,
    "Total Speed"               REAL,
    "Performance(0 - 100 )KM/H" REAL,
    "Cars Prices"               REAL,
    "Fuel Types"                TEXT,
    Seats                       REAL,
    Torque                      REAL
);
"""

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "..", "data", "cars.db")



#PIPELINE
MODEL = "gpt-4.1-mini"
API_KEY= os.getenv("OPENAI_API_KEY")
if not API_KEY:
        print("💡 OpenAI API key not found.")
        api_key = getpass.getpass("🔑 Please enter your OpenAI API key: ")

MAX_TOKENS = 1024

#SYSTEM MESSAGE
SYSTEM_MESSAGE = "You are a helpful AI assistant that assist user on cars using provided supporting documents and conversation history to assist the user"



NEW_USER_MESSAGE_TEMPLATE = """
**Primary Goal:** Answer the user's question based on the context and given information.

---

**Instructions:**

1. **Analyze the provided information.** First, determine if the provided data and the conversation history are sufficient to answer the user's question.

* If **YES**, based on the provided data and the CONVERSATION HISTORY, give the user a well-organized, concise, and simple answer.

    IMPORTANT:  
    + Use the CONVERSATION HISTORY fully to understand the context and answer the user's question.  
    + ALWAYS resolve ambiguous references (e.g., "the V6", "that car", "it", "one", "these", etc.) by referring to PRIOR CONVERSATION HISTORY.  
      Example: If the user says “Are there anything from BMW comparable to that?”, "that" refers to the last car discussed.  
    + Do NOT ask the user again for information already provided in prior questions or answers.  
    + When the user asks for a comparison, if they've recently asked about a specific car, use that model as the basis for comparison unless they specify otherwise.

* If **NO**, proceed to step 2.

2. **Request more data.** Determine if you have already requested more information from the database during this call (i.e., whether the database returned 'no_matching_result_found')

* If **YES**, politely ask the user for more information based on the database schema or explain why their question cannot be answered.

* If **NO**, return 'GENERATE_SQL' with the fewest and most suitable SQL queries needed to retrieve the required car information based on the user's query, the chat history, and the table definition — these queries must be executable in Python using SQLite3.

- For **NO** in step 2, please consider the following when generating your SQL queries:

    - Use the user's previous questions and the chat history to guide your SQL query formation.  
    - For the columns Company Names, Cars Names, Engines, and Fuel Types, the user query might only partially match the values, so use the `LIKE` operator for those columns.  
      For example:  
        - Querying "hybrid" in Fuel Type might match "Petrol (Hybrid)".  
        - Querying "kia forte" could match "Kia" in Company Names and "Forte" (e.g., "Forte LXS") in Cars Names.  
    - Remember to split the company name and the car name separately.  
      For example, "Acura TLX" should be split to "Acura" (Company Names) and "TLX" (Cars Names).

Generate the SQL queries accordingly.

---

**Database Schema**

{{ table_definition }}

**Conversation History**

{% for message in memories %}
{{ message.role }}:{{ message.text }}
{% endfor %}

**Database Information**

{% for row in sql_results %}
{{ row }}
{% endfor %}

**User's Question:**

{{ question }}

---

**IMPORTANT:**  
-If the data or conversation history is insufficient to answer the question, output ONLY the SQL query, prefixed by 'GENERATE_SQL:' with no other text, explanation, or clarification.
Stop generating SQL query immediately after you got enough information.
-Keep the answer well-organized, short, and concise, typically less than 512 tokens unless specified differently by the query.

For example:  
GENERATE_SQL: SELECT * FROM cars2025 WHERE "Cars Prices" <= 60000 AND "Car Types" LIKE '%sedan%';

#Note: If the user's question cannot be answered by the database, USE YOUR BEST OF KNOWLEDGE to answer the question or ask the user to clarify or provide more information.  
#Note: If the information you need for one car is not available, advise the user based on the rest of the available information.
#Note: When the user search for a query like 'what is the best car for a family of 6', you could possibly generalize the query and search for everything that have more than 6 seats.

**Your Response:**

"""



ANS_ROUTES = [
    {
        "condition": "{{ 'GENERATE_SQL:' in replies[0].text }}",
        "output": "{{ replies }}",
        "output_name": "generate_sql_query",
        "output_type": list[str]
    },
    {
        "condition": "{{ 'GENERATE_SQL:' not in replies[0].text }}",
        "output": "{{ replies }}",
        "output_name": "continue",
        "output_type": list[str]
    }
]



#Gradio
THEME = gr.themes.Soft()
TITLE = "Your Personal Car Assistant"
SHARE = False