from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import run_model_tool_loop
from env_loader import load_lab_env
from providers import make_provider
from security import redact_sensitive_values
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
PROMPT_PATH = ARTIFACTS_DIR / "system_prompt.md"
TOOLS_PATH = ARTIFACTS_DIR / "tools.yaml"
TRANSCRIPTS_DIR = ARTIFACTS_DIR / "evidence" / "transcripts"
PROVIDER_KEYS = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_transcript() -> tuple[dict[str, Any], Path]:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = f"v3_ui_{timestamp}"
    artifact = build_artifact_version("v3", PROMPT_PATH, TOOLS_PATH)
    payload = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }
    return payload, TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"


def write_transcript(payload: dict[str, Any], path: Path) -> None:
    payload["updated_at"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation" not in st.session_state:
        st.session_state.conversation = []
    if "transcript" not in st.session_state:
        transcript, path = new_transcript()
        st.session_state.transcript = transcript
        st.session_state.transcript_path = path


def reset_state() -> None:
    transcript, path = new_transcript()
    st.session_state.messages = []
    st.session_state.conversation = []
    st.session_state.transcript = transcript
    st.session_state.transcript_path = path


def render_reply(text: str) -> None:
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        st.markdown(text or "Không có nội dung trả lời.")
        return

    required = {"intent", "action", "reply", "evidence_ids"}
    if not isinstance(payload, dict) or set(payload) != required:
        st.code(text, language="json")
        return

    st.markdown(str(payload["reply"]))
    meta = st.columns(2)
    meta[0].caption(f"Intent: {payload['intent']}")
    meta[1].caption(f"Action: {payload['action']}")
    evidence = payload.get("evidence_ids") or []
    if evidence:
        st.caption("Evidence: " + ", ".join(str(item) for item in evidence))


def render_trace(rounds: list[dict[str, Any]]) -> None:
    if not rounds:
        st.caption("Không có tool call.")
        return
    for round_item in rounds:
        calls = round_item.get("tool_calls") or []
        results = round_item.get("tool_results") or []
        st.markdown(f"**Round {round_item.get('round')}**")
        if not calls:
            st.caption("Model trả lời trực tiếp.")
        for index, call in enumerate(calls):
            name = call.get("name", "unknown_tool")
            result = results[index].get("result", {}) if index < len(results) else {}
            status = "error" if isinstance(result, dict) and result.get("error") else "ok"
            with st.expander(f"{name} [{status}]", expanded=status == "error"):
                args_col, result_col = st.columns(2)
                with args_col:
                    st.caption("Arguments")
                    st.json(call.get("args") or {})
                with result_col:
                    st.caption("Result")
                    st.json(result)


def render_message(message: dict[str, Any]) -> None:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_reply(message.get("content", ""))
            with st.expander("Tool trace", expanded=False):
                render_trace(message.get("rounds") or [])
        else:
            st.markdown(message.get("content", ""))
            if message.get("redacted"):
                st.caption("Giá trị nhạy cảm đã được thay bằng [REDACTED].")


st.set_page_config(
    page_title="Northstar Helpdesk Console",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)
load_lab_env(ROOT)
init_state()

st.markdown(
    """
    <style>
    :root {
      --canvas: #f3f6fa;
      --surface: #fbfcfe;
      --surface-muted: #e9eff6;
      --text: #172133;
      --muted: #526176;
      --line: #cbd6e3;
      --accent: #245b9e;
      --accent-strong: #174779;
      --radius: 12px;
    }
    .stApp { background: var(--canvas); color: var(--text); }
    [data-testid="stHeader"] { background: color-mix(in srgb, var(--canvas) 92%, transparent); }
    [data-testid="stSidebar"] { background: var(--surface-muted); border-right: 1px solid var(--line); }
    [data-testid="stChatMessage"] {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      margin-bottom: 0.8rem;
    }
    [data-testid="stChatInput"] textarea {
      background: var(--surface);
      color: var(--text);
      border-color: var(--line);
      border-radius: var(--radius);
    }
    .stButton > button {
      border-radius: var(--radius);
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #f7f9fc;
      white-space: nowrap;
    }
    .stButton > button:hover { background: var(--accent-strong); color: #f7f9fc; }
    .stButton > button:active { transform: translateY(1px); }
    :focus-visible { outline: 3px solid #6f96c7 !important; outline-offset: 2px; }
    code, pre, [data-testid="stJson"] { font-family: Consolas, "Cascadia Mono", monospace; }
    .console-header {
      padding: 0.35rem 0 1rem;
      border-bottom: 1px solid var(--line);
      margin-bottom: 1.25rem;
    }
    .console-header h1 { margin: 0; font-size: clamp(1.7rem, 3vw, 2.45rem); letter-spacing: -0.035em; }
    .console-header p { margin: 0.4rem 0 0; color: var(--muted); max-width: 68ch; }
    @media (max-width: 767px) {
      .block-container { padding-left: 1rem; padding-right: 1rem; }
      [data-testid="column"] { min-width: 100% !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
tool_declarations = load_tool_declarations(TOOLS_PATH)
openai_tools = to_openai_tools(tool_declarations)
artifact = build_artifact_version("v3", PROMPT_PATH, TOOLS_PATH)

with st.sidebar:
    st.subheader("Runtime")
    provider_name = st.selectbox("Provider", list(PROVIDER_KEYS), index=0)
    model_override = st.text_input("Model override", help="Để trống để dùng model mặc định của provider.")
    max_tool_rounds = st.slider("Số tool rounds tối đa", min_value=1, max_value=6, value=4)
    key_name = PROVIDER_KEYS[provider_name]
    if os.getenv(key_name):
        st.success(f"{key_name} đã được nạp.")
    else:
        st.error(f"Thiếu {key_name} trong .env.")
    st.divider()
    st.caption("Artifact đang chạy")
    st.code(artifact.artifact_version, language=None)
    st.caption(f"Prompt: {artifact.prompt_hash[:12]}")
    st.caption(f"Tools: {artifact.tools_hash[:12]}")
    st.caption(f"Transcript: {st.session_state.transcript_path}")
    if st.button("Cuộc hội thoại mới", use_container_width=True):
        reset_state()
        st.rerun()

st.markdown(
    """
    <div class="console-header">
      <h1>Northstar Helpdesk Console</h1>
      <p>Kiểm tra dịch vụ, thiết bị, policy và ticket với trace có thể audit.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.messages:
    st.info("Bắt đầu bằng một yêu cầu IT. Ví dụ: Kiểm tra VPN production và máy LT-204.")

for saved_message in st.session_state.messages:
    render_message(saved_message)

user_text = st.chat_input("Nhập yêu cầu helpdesk, không nhập password, token hoặc mã MFA")
if user_text:
    safe_text, was_redacted = redact_sensitive_values(user_text)
    user_message = {"role": "user", "content": safe_text, "redacted": was_redacted}
    st.session_state.messages.append(user_message)
    render_message(user_message)

    if not os.getenv(PROVIDER_KEYS[provider_name]):
        error_text = f"Thiếu {PROVIDER_KEYS[provider_name]}. Hãy cấu hình starter_v0/.env rồi thử lại."
        assistant_message = {"role": "assistant", "content": error_text, "rounds": []}
        st.session_state.messages.append(assistant_message)
        render_message(assistant_message)
        st.stop()

    messages = [
        {"role": "system", "content": system_prompt},
        *st.session_state.conversation[-10:],
        {"role": "user", "content": safe_text},
    ]
    started_at = now_iso()
    try:
        with st.status("Đang phân tích và chạy tool...", expanded=False) as status:
            provider = make_provider(provider_name)
            result = run_model_tool_loop(
                provider=provider,
                messages=messages,
                tools=openai_tools,
                model=model_override or None,
                max_tool_rounds=max_tool_rounds,
            )
            status.update(label="Đã hoàn tất", state="complete")
        assistant_text = result.get("assistant_text") or ""
        assistant_message = {
            "role": "assistant",
            "content": assistant_text,
            "rounds": result.get("rounds") or [],
            "status": result.get("status"),
        }
        st.session_state.messages.append(assistant_message)
        st.session_state.conversation.extend([
            {"role": "user", "content": safe_text},
            {"role": "assistant", "content": assistant_text},
        ])
        turn = {
            "turn_index": len(st.session_state.transcript["turns"]) + 1,
            "started_at": started_at,
            "ended_at": now_iso(),
            "provider": provider_name,
            "model": model_override or getattr(provider, "default_model", None),
            "user": safe_text,
            "sensitive_input_redacted": was_redacted,
            **result,
        }
    except Exception as exc:
        assistant_message = {
            "role": "assistant",
            "content": f"Provider error: {type(exc).__name__}: {exc}",
            "rounds": [],
            "status": "provider_error",
        }
        st.session_state.messages.append(assistant_message)
        turn = {
            "turn_index": len(st.session_state.transcript["turns"]) + 1,
            "started_at": started_at,
            "ended_at": now_iso(),
            "provider": provider_name,
            "model": model_override or None,
            "user": safe_text,
            "sensitive_input_redacted": was_redacted,
            "status": "provider_error",
            "error": f"{type(exc).__name__}: {exc}",
            "rounds": [],
            "tool_events": [],
        }

    st.session_state.transcript["turns"].append(turn)
    write_transcript(st.session_state.transcript, st.session_state.transcript_path)
    st.rerun()
