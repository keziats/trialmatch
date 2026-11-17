"""Chatbox: ask questions about the study in plain language."""
import anthropic
import streamlit as st

from neurovation import chat, state, ui
from trialmatch.llm import get_client

ss = state.ss()
if not state.matched():
    st.warning("Submit a protocol first.", icon=":material/lock:")
    st.stop()

client = get_client()
ss.setdefault("nv_chat", [])       # what is shown
ss.setdefault("nv_chat_api", [])   # full API history, including tool calls

ui.header("Chatbox", "Ask about patients, eligibility, evidence or recruitment progress. Answers come from the study data, with patient and criterion IDs.",
          [state.protocol_name(), "Chatbox"])

top = st.columns([3, 1])
if client:
    top[0].success(f"Connected to Claude ({chat.MODEL}). Every answer is looked up in the study data.", icon=":material/check_circle:")
else:
    top[0].info("Offline answers. Add ANTHROPIC_API_KEY to the app's secrets for free-form questions answered by Claude.", icon=":material/info:")
if top[1].button("Clear chat", icon=":material/delete_sweep:", width="stretch", disabled=not ss.nv_chat):
    ss.nv_chat, ss.nv_chat_api = [], []
    st.rerun()

SUGGEST = ["Who are the strongest candidates?", "Tell me about patient 2", "Why are patients excluded?",
           "Who is one criterion short?", "What do the notes most often leave out?", "Where are we with consent?"]
if not ss.nv_chat:
    st.caption("Try one of these:")
    cols = st.columns(3)
    for i, s in enumerate(SUGGEST):
        if cols[i % 3].button(s, key=f"sg_{i}", width="stretch"):
            ss.nv_pending = s
            st.rerun()

for msg in ss.nv_chat:
    with st.chat_message(msg["role"], avatar=":material/person:" if msg["role"] == "user" else ":material/neurology:"):
        st.markdown(msg["text"])
        if msg.get("tools"):
            st.caption("Looked up: " + ", ".join(dict.fromkeys(t.replace("_", " ") for t in msg["tools"])))

question = st.chat_input("Ask about a patient, a criterion, or recruitment progress…") or ss.pop("nv_pending", None)
if question:
    ss.nv_chat.append({"role": "user", "text": question})
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(question)
    with st.chat_message("assistant", avatar=":material/neurology:"):
        tools = []
        with st.spinner("Looking it up…"):
            if client:
                n_before = len(ss.nv_chat_api)
                try:
                    answer, tools = chat.ask_claude(client, ss.nv_chat_api, question)
                except anthropic.AuthenticationError:
                    del ss.nv_chat_api[n_before:]
                    answer = "The API key was rejected. Check ANTHROPIC_API_KEY in the app's secrets.\n\n" + chat.ask_offline(question)
                except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
                    del ss.nv_chat_api[n_before:]
                    answer = f"Claude is unavailable right now ({type(exc).__name__}); here is the offline answer.\n\n" + chat.ask_offline(question)
            else:
                answer = chat.ask_offline(question)
        st.markdown(answer)
        if tools:
            st.caption("Looked up: " + ", ".join(dict.fromkeys(t.replace("_", " ") for t in tools)))
    ss.nv_chat.append({"role": "assistant", "text": answer, "tools": tools})
    state.log("Chatbox question", None, question)
