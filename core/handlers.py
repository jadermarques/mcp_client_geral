import streamlit as st
from langchain_core.messages import HumanMessage
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.messages.tool import ToolMessage
from utils import astream_graph
from langchain_core.runnables import RunnableConfig

def print_message():
    i = 0
    while i < len(st.session_state.history):
        message = st.session_state.history[i]
        if message["role"] == "user":
            st.chat_message("user", avatar="🧑‍💻").markdown(message["content"])
            i += 1
        elif message["role"] == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(message["content"])
                if i + 1 < len(st.session_state.history) and st.session_state.history[i + 1]["role"] == "assistant_tool":
                    with st.expander("🔧 Tool Call Information", expanded=False):
                        st.markdown(st.session_state.history[i + 1]["content"])
                    i += 2
                else:
                    i += 1
        else:
            i += 1

def get_streaming_callback(text_placeholder, tool_placeholder):
    accumulated_text = []
    accumulated_tool = []

    def callback_func(message: dict):
        nonlocal accumulated_text, accumulated_tool
        message_content = message.get("content", None)

        if isinstance(message_content, AIMessageChunk):
            content = message_content.content
            if isinstance(content, list) and len(content) > 0:
                if content[0]["type"] == "text":
                    accumulated_text.append(content[0]["text"])
                    text_placeholder.markdown("".join(accumulated_text))
            elif isinstance(content, str):
                accumulated_text.append(content)
                text_placeholder.markdown("".join(accumulated_text))
        elif isinstance(message_content, ToolMessage):
            accumulated_tool.append("\n```json\n" + str(message_content.content) + "\n```\n")
            with tool_placeholder.expander("🔧 Tool Call Information", expanded=True):
                st.markdown("".join(accumulated_tool))
        return None

    return callback_func, accumulated_text, accumulated_tool

async def process_query(query, text_placeholder, tool_placeholder, timeout_seconds=60):
    try:
        if st.session_state.agent:
            callback, acc_text, acc_tool = get_streaming_callback(text_placeholder, tool_placeholder)
            response = await astream_graph(
                st.session_state.agent,
                {"messages": [HumanMessage(content=query)]},
                callback=callback,
                config=RunnableConfig(
                    recursion_limit=st.session_state.recursion_limit,
                    thread_id=st.session_state.thread_id,
                ),
            )
            return response, "".join(acc_text), "".join(acc_tool)
        else:
            return {"error": "🚫 Agent not initialized."}, "", ""
    except Exception as e:
        import traceback
        return {"error": f"❌ Error: {str(e)}\n{traceback.format_exc()}"}, "", ""
