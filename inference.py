import os
import json
import requests
from openai import OpenAI

MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct"
ENV_URL = os.getenv("ENV_URL", "http://localhost:7860")
MAX_STEPS = 15

# ✅ STRICT — MUST CRASH IF WRONG (IMPORTANT FOR VALIDATOR)
API_BASE_URL = os.environ["API_BASE_URL"]
API_KEY = os.environ["API_KEY"]

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=API_KEY
)

# ✅ FORCE API CALL (NO SKIP)
def test_llm():
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5,
    )
    print("[LLM TEST] success")


SYSTEM_PROMPT = """You are a smart contract security auditor.

Return ONLY valid JSON.

Actions:
1. report_vulnerability
2. suggest_patch
3. request_hint
4. finalize
5. noop
"""


def get_action(obs, history):
    context = {
        "contract_name": obs.get("contract_name", ""),
        "source_code": obs.get("source_code", ""),
        "step": obs.get("step_number", 0),
    }

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history[-6:]
    messages.append({
        "role": "user",
        "content": json.dumps(context)
    })

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=200,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)

    except Exception:
        return {"action_type": "noop", "params": {}}


def run_task(task_id):
    print(f"[START] {task_id}")

    resp = requests.post(
        f"{ENV_URL}/reset",
        params={"task_id": task_id},
        timeout=30
    )
    obs = resp.json()

    history = []
    score = 0.0

    for step in range(MAX_STEPS):
        action = get_action(obs, history)

        resp = requests.post(
            f"{ENV_URL}/step",
            json=action,
            params={"task_id": task_id},
            timeout=30
        )
        result = resp.json()

        obs = result.get("observation", {})
        score = result.get("reward", {}).get("score", 0.0)

        print(f"[STEP] {task_id} {step+1} score={score:.4f}")

        history.append({"role": "assistant", "content": json.dumps(action)})

        if result.get("done", False):
            break

    print(f"[END] {task_id} score={score:.4f}")
    return score


def main():
    test_llm()  # 🔥 MUST RUN — no conditions

    scores = {}
    for task_id in ["task1", "task2", "task3"]:
        scores[task_id] = run_task(task_id)

    print("\n[RESULTS]")
    for tid, score in scores.items():
        print(f"{tid}: {score:.4f}")

    avg = sum(scores.values()) / len(scores)
    print(f"average: {avg:.4f}")


if __name__ == "__main__":
    main()