import streamlit as st
import asyncio
import nest_asyncio
import json
import os
import platform
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from utils import astream_graph, random_uuid
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.messages.tool import ToolMessage

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
nest_asyncio.apply()

if "event_loop" not in st.session_state:
    loop = asyncio.new_event_loop()
    st.session_state.event_loop = loop
    asyncio.set_event_loop(loop)

load_dotenv(override=True)

CONFIG_FILE_PATH = "config.json"

def load_config_from_json():
    default_config = {
        "get_current_time": {
            "command": "python",
            "args": ["./mcp_server_time.py"],
            "transport": "stdio"
        }
    }
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            save_config_to_json(default_config)
            return default_config
    except Exception as e:
        st.error(f"Error loading settings file: {str(e)}")
        return default_config

def save_config_to_json(config):
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving settings file: {str(e)}")
        return False

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

use_login = os.environ.get("USE_LOGIN", "false").lower() == "true"

if use_login and not st.session_state.authenticated:
    st.set_page_config(page_title="Agent with MCP Tools", page_icon="🧠")
else:
    st.set_page_config(page_title="Agent with MCP Tools", page_icon="🧠", layout="wide")

if use_login and not st.session_state.authenticated:
    st.title("🔐 Login")
    st.markdown("Login is required to use the system.")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if username == os.environ.get("USER_ID") and password == os.environ.get("USER_PASSWORD"):
                st.session_state.authenticated = True
                st.success("✅ Login successful! Please wait...")
                st.rerun()
            else:
                st.error("❌ Username or password is incorrect.")
    st.stop()

st.sidebar.markdown("### ✍️ Made by [TeddyNote](https://youtube.com/c/teddynote) 🚀")
st.sidebar.markdown("### 💻 [Project Page](https://github.com/teddynote-lab/langgraph-mcp-agents)")
st.sidebar.divider()

st.title("💬 MCP Tool Utilization Agent")
st.markdown("✨ Ask questions to the ReAct agent that utilizes MCP tools.")

SYSTEM_PROMPT = """<ROLE>
You are a smart agent with an ability to use tools. 
...
</OUTPUT_FORMAT>
"""

OUTPUT_TOKEN_INFO = {
    "gpt-4o-mini": {"max_tokens": 16000},
    "claude-3-5-sonnet-latest": {"max_tokens": 8192},
    "claude-3-5-haiku-latest": {"max_tokens": 8192},
    "claude-3-7-sonnet-latest": {"max_tokens": 64000},
    "gpt-4o": {"max_tokens": 16000},
    "gpt-4o-mini-2024-07-18": {"max_tokens": 16000},
}

if "session_initialized" not in st.session_state:
    st.session_state.session_initialized = False
    st.session_state.agent = None
    st.session_state.history = []
    st.session_state.mcp_client = None
    st.session_state.timeout_seconds = 120
    st.session_state.selected_model = "gpt-4o-mini"
    st.session_state.recursion_limit = 100

if "thread_id" not in st.session_state:
    st.session_state.thread_id = random_uuid()

async def cleanup_mcp_client():
    if "mcp_client" in st.session_state and st.session_state.mcp_client is not None:
        try:
            await st.session_state.mcp_client.__aexit__(None, None, None)
            st.session_state.mcp_client = None
        except Exception:
            pass

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
                if (
                    i + 1 < len(st.session_state.history)
                    and st.session_state.history[i + 1]["role"] == "assistant_tool"
                ):
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
            if isinstance(content, str):
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
            streaming_callback, acc_text, acc_tool = get_streaming_callback(text_placeholder, tool_placeholder)
            response = await asyncio.wait_for(
                astream_graph(
                    st.session_state.agent,
                    {"messages": [HumanMessage(content=query)]},
                    callback=streaming_callback,
                    config=RunnableConfig(
                        recursion_limit=st.session_state.recursion_limit,
                        thread_id=st.session_state.thread_id,
                    ),
                ),
                timeout=timeout_seconds,
            )
            return response, "".join(acc_text), "".join(acc_tool)
        else:
            return {"error": "🚫 Agent has not been initialized."}, "", ""
    except Exception as e:
        import traceback
        return {"error": f"❌ Error occurred: {str(e)}\n{traceback.format_exc()}"}, "", ""



import traceback

async def initialize_session(mcp_config=None):
    """
    Inicializa o cliente MCP e o agente, com logs por ferramenta.
    Exibe quais ferramentas foram carregadas e quais falharam.
    Gera logs no terminal para diagnóstico detalhado.
    """
    with st.spinner("🔄 Connecting to MCP server..."):
        await cleanup_mcp_client()

        if mcp_config is None:
            mcp_config = load_config_from_json()

        st.write("🧪 Testando ferramentas MCP individualmente...")

        working_tools = {}

        for name, config in mcp_config.items():
            if "tool_enabled_flags" in st.session_state:
                if name in st.session_state.tool_enabled_flags and not st.session_state.tool_enabled_flags[name]:
                    print(f"[SKIP] Ferramenta `{name}` está desabilitada. Ignorando.")
                    continue

            st.write(f"🔌 Tentando subir: `{name}`...")
            print(f"[INFO] Iniciando carregamento da ferramenta MCP: {name}")

            try:
                temp_client = MultiServerMCPClient({name: config})
                await temp_client.__aenter__()
                tools = temp_client.get_tools()

                if tools:
                    st.success(f"✅ `{name}` carregada com sucesso.")
                    working_tools[name] = config
                    print(f"[OK] Ferramenta `{name}` carregada com sucesso.")
                else:
                    st.warning(f"⚠️ `{name}` não retornou nenhuma ferramenta.")
                    print(f"[WARN] `{name}` não retornou ferramentas.")
                
                await temp_client.__aexit__(None, None, None)

            except Exception as e:
                st.error(f"❌ Falha ao carregar `{name}`: {e}")
                print(f"\n[ERRO] Falha ao carregar servidor MCP: {name}")
                print(f"Mensagem: {e}")
                print("Stack trace completo:")
                traceback.print_exc()

        if not working_tools:
            st.error("❌ Nenhuma ferramenta foi carregada. Verifique seu config.json ou o terminal.")
            return False

        st.write("🔁 Inicializando cliente final com ferramentas funcionais...")

        try:
            final_client = MultiServerMCPClient(working_tools)
            await final_client.__aenter__()
            tools = final_client.get_tools()
            st.session_state.tool_count = len(tools)
            st.session_state.mcp_client = final_client

            selected_model = st.session_state.selected_model
            if selected_model.startswith("claude"):
                model = ChatAnthropic(
                    model=selected_model,
                    temperature=0.1,
                    max_tokens=OUTPUT_TOKEN_INFO[selected_model]["max_tokens"],
                )
            else:
                model = ChatOpenAI(
                    model=selected_model,
                    temperature=0.1,
                    max_tokens=OUTPUT_TOKEN_INFO[selected_model]["max_tokens"],
                )

            agent = create_react_agent(
                model,
                tools,
                checkpointer=MemorySaver(),
                prompt=SYSTEM_PROMPT,
            )

            st.session_state.agent = agent
            st.session_state.session_initialized = True
            st.success("✅ Sessão inicializada com sucesso.")
            print("[OK] Sessão MCP inicializada com sucesso.")
            return True

        except Exception as final_error:
            st.error(f"❌ Erro ao inicializar agente final: {final_error}")
            print(f"[ERRO] Falha na inicialização final do agente: {final_error}")
            traceback.print_exc()
            return False





# --- Sidebar ---
with st.sidebar:
    st.subheader("⚙️ System Settings")
    available_models = []
    if os.getenv("ANTHROPIC_API_KEY"):
        available_models.extend(["claude-3-7-sonnet-latest", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"])
    if os.getenv("OPENAI_API_KEY"):
        available_models.extend(["gpt-4o", "gpt-4o-mini"])
    if not available_models:
        st.warning("⚠️ API keys are not configured.")
        available_models = ["claude-3-7-sonnet-latest"]

    previous_model = st.session_state.selected_model
    st.session_state.selected_model = st.selectbox(
        "🤖 Select model to use",
        options=available_models,
        index=available_models.index(previous_model) if previous_model in available_models else 0
    )

    if previous_model != st.session_state.selected_model and st.session_state.session_initialized:
        st.warning("⚠️ Model has been changed. Click 'Apply Settings' to apply changes.")

    st.session_state.timeout_seconds = st.slider("⏱️ Timeout (seconds)", 60, 300, st.session_state.timeout_seconds, 10)
    st.session_state.recursion_limit = st.slider("🔁 Recursion Limit", 10, 200, st.session_state.recursion_limit, 10)

    st.subheader("🔧 Tools")
    if "pending_mcp_config" not in st.session_state:
        st.session_state.pending_mcp_config = load_config_from_json()

    tool_json = st.text_area("Paste tool JSON", height=150)
    if st.button("Add Tool"):
        try:
            parsed = json.loads(tool_json)
            if "mcpServers" in parsed:
                parsed = parsed["mcpServers"]
            st.session_state.pending_mcp_config.update(parsed)
            st.success("✅ Tool(s) added. Click 'Apply Settings'.")
        except Exception as e:
            st.error(f"❌ Invalid JSON: {e}")

    with st.expander("📋 Registered Tools"):
        for tool in list(st.session_state.pending_mcp_config.keys()):
            if "tool_enabled_flags" not in st.session_state:
                st.session_state.tool_enabled_flags = {}
            if tool not in st.session_state.tool_enabled_flags:
                st.session_state.tool_enabled_flags[tool] = True  # inicia como ativo

            is_enabled = st.session_state.tool_enabled_flags[tool]
            status_icon = "🟢" if is_enabled else "🔴"
            toggle_label = f"{status_icon} `{tool}`"

            col1, col2, col3 = st.columns([8, 1, 1])
            if col1.button(toggle_label, key=f"toggle_{tool}", help="Click to enable/disable", use_container_width=True):
                st.session_state.tool_enabled_flags[tool] = not is_enabled
                st.rerun()
            if col2.button("🗑️", key=f"del_{tool}", help="Delete tool", use_container_width=True):
                del st.session_state.pending_mcp_config[tool]
                if tool in st.session_state.tool_enabled_flags:
                    del st.session_state.tool_enabled_flags[tool]
                st.rerun()


    st.divider()
    st.subheader("📊 Info")
    st.write(f"🛠️ Tools: {st.session_state.get('tool_count', '...')}")
    st.write(f"🧠 Model: {st.session_state.selected_model}")

    if st.button("Apply Settings", type="primary"):
        save_config_to_json(st.session_state.pending_mcp_config)
        st.session_state.agent = None
        st.session_state.session_initialized = False
        success = st.session_state.event_loop.run_until_complete(
            initialize_session(st.session_state.pending_mcp_config)
        )
        if success:
            st.success("✅ Settings applied.")
        else:
            st.error("❌ Initialization failed.")
        st.rerun()

    if st.button("Reset Conversation", type="secondary"):
        st.session_state.thread_id = random_uuid()
        st.session_state.history = []
        st.rerun()

    if use_login and st.session_state.authenticated:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.rerun()

# --- Main ---
if not st.session_state.session_initialized:
    st.info("Click 'Apply Settings' to start.")

print_message()

query = st.chat_input("💬 Enter your question")
if query and st.session_state.session_initialized:
    st.chat_message("user", avatar="🧑‍💻").markdown(query)
    with st.chat_message("assistant", avatar="🤖"):
        tool_placeholder = st.empty()
        text_placeholder = st.empty()
        resp, final_text, final_tool = st.session_state.event_loop.run_until_complete(
            process_query(query, text_placeholder, tool_placeholder, st.session_state.timeout_seconds)
        )
    if "error" in resp:
        st.error(resp["error"])
    else:
        st.session_state.history.append({"role": "user", "content": query})
        st.session_state.history.append({"role": "assistant", "content": final_text})
        if final_tool.strip():
            st.session_state.history.append({"role": "assistant_tool", "content": final_tool})
        st.rerun()
