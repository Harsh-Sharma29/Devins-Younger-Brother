import os
import uuid
from dotenv import load_dotenv

# Force load the .env file
load_dotenv(override=True)

# Quick startup validation check
if not os.getenv("GROQ_API_KEY"):
    raise ValueError("❌ FATAL: GROQ_API_KEY is not loaded from .env!")
else:
    print("✅ Groq API Key loaded successfully.")

from src.core.checkpointer import get_app, cleanup_resources
from src.core.config import build_run_config, DEFAULT_RECURSION_LIMIT
from src.core.graph import get_initial_state

DEFAULT_PROMPT = (
    "Write a python script that calls a mock API at 'https://api.example.com/data' "
    "using the requests library, parses the JSON response, and handles the potential "
    "missing 'items' key error. Make sure to intentionally pass an un-imported module "
    "name or a syntax error in the first line so that it fails initially."
)


def main():
    print("🚀 Initializing AutoForge...\n" + "-" * 40)

    thread_id = os.getenv("AUTOFORGE_THREAD_ID", "").strip() or str(uuid.uuid4())
    run_config = build_run_config(thread_id, recursion_limit=DEFAULT_RECURSION_LIMIT)
    initial_state = get_initial_state(DEFAULT_PROMPT)

    print(f"👤 User Prompt: {initial_state['user_prompt']}")
    print(f"🧵 thread_id:     {thread_id}")
    print(f"⚙️  recursion_limit: {run_config['recursion_limit']}")
    print("⏳ Invoking LangGraph pipeline (Postgres checkpointer)...\n")

    try:
        app = get_app()
        final_state = app.invoke(initial_state, config=run_config)

        if hasattr(final_state, "model_dump"):
            state_dict = final_state.model_dump()
        elif hasattr(final_state, "dict"):
            state_dict = final_state.dict()
        else:
            state_dict = final_state

        print("✅ Pipeline execution completed!\n")
        print("====== FINAL STATE OVERVIEW ======")
        print(f"Planner Suggestion: {state_dict.get('planner_suggestion')}\n")
        print(f"Updated User Prompt:\n{state_dict.get('user_prompt')}\n")
        print(f"Terminal Output: {state_dict.get('terminal_output')}")
        print(f"Detected Errors: {state_dict.get('detected_errors')}")
        print(f"Repair Attempts: {state_dict.get('repair_attempts', 0)}")
        print(f"Intent:          {state_dict.get('intent')}")
        print(f"Is Verified:     {state_dict.get('is_verified')}\n")
        print(f"History turns:   {len(state_dict.get('conversation_history') or [])}\n")

        print("====== 💻 GENERATED CODE BUFFER 💻 ======")
        code_buffer = state_dict.get("code_buffer", "")
        if code_buffer:
            print(code_buffer)
        else:
            print("[No code was generated]")
        print("=========================================")

    except Exception as e:
        print(f"❌ Error during graph invocation: {e}")
    finally:
        cleanup_resources()


if __name__ == "__main__":
    main()
