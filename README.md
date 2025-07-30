Car Information Chatbot Report
Overview

This project creates a conversational AI assistant that answers car-related queries using a structured SQLite database with 2025 car information. The system uses Haystack to integrate OpenAI LLM for both SQL query and response generation and manages in-memory chat sessions to provide the model with contextual understanding.

System Structure
2.1 Components
OpenAI: Provides both natural language and SQL query logic responses.
SQLite Database: Car data source
Why use SQL and not ElasticSearch: Because it is a structured database with a large number of numerical values, using SQL is best for queries like “What is the best sedan under $50,000?”
In-memory chat store: Stores previous conversations, including both query and response, to provide context to the model.
Custom components: 1 component for executing SQL queries and a message weaving component to store the current query-response pair as a block.
2.2 Data Flow:
User Query: Enter through a user-friendly interface, then get sent to the pipeline
Prompt/Message Building:  User queries, chat history, and SQLite search results are composed to create a message.
LLM Prompting: Gemini decides whether it can answer the question directly or needs to generate SQL queries to gather more information.
Routing:
If SQL Data needed: LLM outputs queries, which are run through the custom SQL Query executer component
Else: LLM provides a direct response
Response assembly: A contextual reply is built and added to chat memory.
Gradio interface: user then get a simple and well-structured response and the program wait for the next query

Key Modules
Pipeline Structure
class ChatSearch:
   def __init__(self, session_id="default_session", chat_memory=None):
       self.session_id = session_id
       assert chat_memory is not None, "Must provide chat_memory!"
       self._chat_memory = chat_memory
       self._pipeline = self._setup_pipeline()






   def _setup_pipeline(self):
       self.memory_retriever = ChatMessageRetriever(self._chat_memory)
       self.memory_writer = ChatMessageWriter(self._chat_memory)
       memory_joiner = ListJoiner(List[ChatMessage])


       sql_query = SQLQuery(DB_PATH)


       # LLM
       ans_generator = OpenAIChatGenerator(model=MODEL, api_key=Secret.from_token(GEMINI_API_KEY), generation_kwargs={"max_tokens": MAX_TOKENS})


       # Prompt Builder
       ans_prompt_builder = ChatPromptBuilder(variables=["question", "sql_results", "memories", "table_definition"],
                                          required_variables=["table_definition"])


       # Router
       ans_router = ConditionalRouter(ANS_ROUTES, unsafe=True)


       # Add component
       pipeline = Pipeline()
       pipeline.add_component("memory_retriever", self.memory_retriever)
       pipeline.add_component("memory_writer", self.memory_writer)
       pipeline.add_component("memory_joiner", memory_joiner)
       pipeline.add_component("sql_query", sql_query)
       pipeline.add_component("ans_generator", ans_generator)
       pipeline.add_component("ans_prompt_builder", ans_prompt_builder)
       pipeline.add_component("ans_router", ans_router)


       # Connect component
       # Connect message history to writer and retriever to prompt builder
       pipeline.connect("memory_joiner", "memory_writer.messages")
       pipeline.connect("memory_retriever", "ans_prompt_builder.memories")


       # connect prompt to ans generator and generator to router
       pipeline.connect("ans_prompt_builder", "ans_generator")
       pipeline.connect("ans_generator.replies", "ans_router.replies")


       # connect router to possible outputs
       pipeline.connect("ans_router.generate_sql_query", "sql_query")
       pipeline.connect("ans_router.continue", "memory_joiner")


       # Connect sql data to prompt
       pipeline.connect("sql_query.results", "ans_prompt_builder.sql_results")


       return pipeline

Feed the query and other information, then return the reply
def gradio_chat(self, message, history):
   messages = [ChatMessage.from_system(SYSTEM_MESSAGE), ChatMessage.from_user(NEW_USER_MESSAGE_TEMPLATE)]
   for msg in history:
       if msg["role"] == "user":
           messages.append(ChatMessage.from_user(msg["content"]))
       elif msg["role"] == "assistant":
           messages.append(ChatMessage.from_assistant(msg["content"]))


   messages.append(ChatMessage.from_user(message))


   result = self._pipeline.run(data={
       "memory_retriever": {},
       "memory_joiner": {"values": [ChatMessage.from_user(message)]},
       "ans_prompt_builder": {
           "template": messages,  # or .prompt if required by your class
           "question": message,
           "table_definition": TABLE_DEFINITION,
       },
       "memory_writer": {},
   }, include_outputs_from=["ans_generator"])


   # Get reply from the result structure (adjust as necessary for your codebase)
   if 'memory_joiner' in result:
       assistant_resp = result['memory_joiner']['messages'][-1]
   else:
       assistant_resp = result['ans_generator']['replies'][0]


   return assistant_resp.text


Router logic
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
Prompt template
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
If the data or conversation history is insufficient to answer the question, output ONLY the SQL query, prefixed by 'GENERATE_SQL:' with no other text, explanation, or clarification.
Stop generating SQL query immediately after you got enough information.


For example: 
GENERATE_SQL: SELECT * FROM cars2025 WHERE "Cars Prices" <= 60000 AND "Car Types" LIKE '%sedan%';


#Note: If the user's question cannot be answered by the database, USE YOUR BEST OF KNOWLEDGE to answer the question or ask the user to clarify or provide more information. 
#Note: If the information you need for one car is not available, advise the user based on the rest of the available information.


**Your Response:**


"""
SQL Table Definition
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

SQLQuery: Executes SQL and returns results
@component
class SQLQuery:
   def __init__(self, db_path: str):
       """
       Initializes the SQLQuery component with the path to the database.
       The connection is established in the run method.
       """
       self.db_path = db_path
       self.disallowed_keywords = {'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER'}


   @component.output_types(results=List[str], queries=List[str])
   def run(self, queries: List[str]) -> dict[str, any]:
       """
       Executes a list of SQL query strings.
       A new database connection is created for each run to ensure data freshness.
       """
       print("Running SQL Query...")
       results = []
       executed_queries = []
       queries = [queries[0].text.removeprefix('GENERATE_SQL').lstrip(':').strip()]




       # Establish the connection inside the run method
       try:
           with sqlite3.connect(self.db_path) as connection:
               for query_block in queries:


                   cleaned_block = query_block.replace("```sql", "").replace("```", "").strip()
                   individual_queries = [q.strip() for q in cleaned_block.split(';') if q.strip()]


                   for query in individual_queries:
                       if any(keyword in query.upper().split() for keyword in self.disallowed_keywords):
                           print(f"Skipping disallowed query: {query}")
                           continue


                       executed_queries.append(query)
                       try:
                           result_df = pd.read_sql_query(query, connection)
                           if not result_df.empty:
                               results.append(result_df.to_markdown(index=False))
                       except Exception as e:
                           print(f"Error executing query: '{query}'\nError: {e}")
                           results.append("")
       except sqlite3.Error as e:
           print(f"Database connection error: {e}")
           # If the connection fails, return empty results.
           return {"results": ['no_matching_result_found'], "queries": executed_queries}




       if len(results) == 0:
           results = ["No_matching_result_found"]


       return {"results": results, "queries": executed_queries}
Intelligent Querying
Partial Search: The prompt template instructs LLM to generate SQL queries using LIKE for text columns such as car/brand name and fuel type to accommodate typos or partial queries.
Contextual Multi-Turn: Conversation memory means later queries can reference earlier context (“that car,” “those requirements,” etc.)

Strengths & Limitations
	Strengths: 
Modular architecture: easily extensible or changeable to apply different data structures.
Capable of managing partial matches and complex queries.
The model can easy understand and relate the new query with the previous questions or responses to generate the best replies
The model initially utilizes database information to answer queries but also flexible to answer queries that are outside the scope of the database.
	Limitations:
Slow response time for some queries
Inconsistency, the result largely depends on the consistency of the LLM
LLM model can’t recall the first few query-replies in Conversation History when the conversation gets too long. 

Demo
Enter your query or 'q' to quit: what is the best performance sedan under 60000

Chatbot: Based on the information for cars under $60,000, the **TOYOTA GR COROLLA** offers the best performance.

*   **Performance (0-100 km/h):** 2.5 seconds
*   **Price:** $36,995

Another great option is the **Tesla Model 3 Performance**, which is a sedan with a 0-100 km/h time of 3.1 seconds and a price of $53,240.

Enter your query or 'q' to quit: are there anything from bmw that is comparible to the gr corolla

Chatbot: Of course! Let's see what BMW has that's comparable to the Toyota GR Corolla.

Based on the information, the **BMW M135i xDrive** is a great comparison. Here's a quick look at how they stack up:

| Feature | Toyota GR Corolla | BMW M135i xDrive |
| :--- | :--- | :--- |
| **Horsepower** | 300 hp | 302 hp |
| **Engine** | I3 Turbo | I4 |
| **Seats** | 5 | 5 |
| **Price** | $36,995 | $30,000 |
| **0-100 km/h** | 2.5 sec | 4.8 sec |

The **BMW M135i xDrive** offers very similar horsepower in the same vehicle class, making it the most comparable option available in the list.
Enter your query or 'q' to quit: how about 7-seaters, what is the fastest one under 60,000

Chatbot: Based on the information I have, the fastest 7-seater car under $60,000 is the **Ford Explorer (2024)**.

It fits your criteria perfectly:
*   **Seats:** 7
*   **Price:** $55,000
*   **Performance (0-100 km/h):** 5.9 seconds

Enter your query or 'q' to quit: are there any option from germany like audi or bmw

Chatbot: Of course! Both Audi and BMW are fantastic German brands with many great options.

To help me find the perfect car for you, could you tell me a bit more about what you're looking for? For instance, are you interested in a sedan or an SUV, a particular price range, or a specific fuel type like electric, hybrid, or petrol?

Enter your query or 'q' to quit: im asking about the fastest 7 seaters under 60,000 from a german make like bmw or audi

Chatbot: Unfortunately, I couldn't find any 7-seater models from BMW or Audi priced under $60,000 in our database.

Would you be interested in:
*   Searching for 7-seaters from other brands within your budget?
*   Looking at other models from BMW or Audi with fewer seats?

Enter your query or 'q' to quit: let's increase the budget to 80k, are there any 7 seaters from german makes

Chatbot: Of course! Increasing the budget to $80,000 opens up some great 7-seater options from German manufacturers. Based on the information I have, here are a few choices for you:

*   **Audi Q7**: A powerful and luxurious option with a V6 engine, priced at **$60,000**.

*   **Volkswagen California**: A very versatile camper van with a diesel engine, priced at **$70,000**.

*   **Volkswagen ID. Buzz**: A unique all-electric van, perfect for a modern family, priced around **$60,000**.

*   **Volkswagen Tiguan Allspace**: A practical and affordable SUV, priced at **$35,000**.

Let me know if you'd like more details on any of these
Conclusion
This chatbot project is a learning experience with the Haystack framework, understanding different components in the pipeline and building a complete Chatbot. There are a few areas that need significant improvement, including building a good flow/pipeline, creating a good template for the LLM model to follow, and implementing data from the database and chat history.
