from chatbot import ChatSearch
from memory_store import GLOBAL_CHAT_MEMORY
import gradio as gr

from config import THEME, TITLE, SHARE

def main():
    session_id = "session1"
    car_search = ChatSearch(session_id=session_id, chat_memory=GLOBAL_CHAT_MEMORY)



    demo = gr.ChatInterface(
        fn= car_search.gradio_chat,
        type="messages",
        title=TITLE,
        theme=THEME
    )

    demo.launch(share=SHARE)


if __name__ == "__main__":
    main()