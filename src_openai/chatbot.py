from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.routers import ConditionalRouter
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.utils import Secret
from haystack_experimental.components.retrievers import ChatMessageRetriever
from haystack_experimental.components.writers import ChatMessageWriter
from haystack.components.joiners import ListJoiner
from haystack.dataclasses import ChatMessage

from config import *
from components import *



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



    def chat(self):
        while True:
            messages = [ChatMessage.from_system(SYSTEM_MESSAGE), ChatMessage.from_user(NEW_USER_MESSAGE_TEMPLATE)]
            query = input("Enter your question or 'q' to quit:")
            if query == "q":
                break
            result = self._pipeline.run(data=
            {
                "memory_retriever": {},
                "memory_joiner": {"values": [ChatMessage.from_user(query)]},
                "ans_prompt_builder": {
                    "template": messages,
                    "question": query,
                    "table_definition": TABLE_DEFINITION,
                },
                "memory_writer": {},
            },
                include_outputs_from=["ans_generator"]
            )
            if 'memory_joiner' in result:
                assistant_resp = result['memory_joiner']['messages'][-1]
                print(f"🤖 {assistant_resp.text}")
            else:
                assistant_resp = result['ans_generator']['replies'][0]
                print(f"🤖 {assistant_resp.text}")



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
