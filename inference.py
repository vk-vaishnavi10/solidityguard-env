import os
import json
import requests

MODEL_NAME = "meta-llama/Meta-Llama-3-70B-Instruct"
ENV_URL = os.getenv("ENV_URL", "http://localhost:7860")
MAX_STEPS = 15

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")

if not API_BASE_URL:
    raise ValueError("API_BASE_URL is missing")
if not API_KEY:
    raise ValueError("API_KEY is missing")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ================================
# TEST LLM
# ================================
def test_llm():
    r = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers=HEADERS,
        json={
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 5
        }
    )
    r.raise_for_status()
    print("[LLM TEST] success")


# ================================
# IMPROVED PROMPT (CRITICAL 🔥)
# ================================
SYSTEM_PROMPT = """You are an expert smart contract auditor.

GOAL:
- Find ALL vulnerabilities (not just one)
- Report them one by one

STRATEGY:
1. Analyze deeply
2. Report vulnerabilities one at a time
3. If stuck → request_hint
4. Only finalize when confident no more issues exist

STRICT JSON FORMAT:
{
  "action_type": "report_vulnerability",
  "params": {
    "vuln_id": "v1",
    "name": "Reentrancy",
    "severity": "high",
    "location": "withdraw",
    "description": "External call before state update"
  }
}

RULES:
- Always use proper fields
- Do NOT repeat same vulnerability
- Do NOT finalize early
"""


# ================================
# GET ACTION
# ================================
def get_action(obs, history):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history[-6:]

    messages.append({
        "role": "user",
        "content": json.dumps({
            "contract_name": obs.get("contract_name"),
            "source_code": obs.get("source_code"),
            "step": obs.get("step_number")
        })
    })

    try:
        r = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers=HEADERS,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "max_tokens": 250,
                "temperature": 0.2
            }
        )

        r.raise_for_status()
        data = r.json()

        raw = data["choices"][0]["message"]["content"]
        raw = raw.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(raw)

        # ✅ enforce schema
        if parsed.get("action_type") == "report_vulnerability":
            p = parsed.get("params", {})

            parsed["params"] = {
                "vuln_id": p.get("vuln_id", "v_temp"),
                "name": p.get("name", "Unknown Vulnerability"),
                "severity": p.get("severity", "medium"),
                "location": p.get("location", "unknown"),
                "description": p.get("description", "Security issue")
            }

        if "action_type" not in parsed:
            return {"action_type": "noop", "params": {}}

        if "params" not in parsed:
            parsed["params"] = {}

        return parsed

    except Exception as e:
        print("[LLM ERROR]", e)
        return {"action_type": "noop", "params": {}}


# ================================
# RUN TASK (UPGRADED 🔥)
# ================================
def run_task(task_id):
    print(f"[START] {task_id}")

    r = requests.post(f"{ENV_URL}/reset", params={"task_id": task_id})
    obs = r.json()

    history = []
    score = 0
    vuln_counter = 1
    reported = set()

    for step in range(MAX_STEPS):
        action = get_action(obs, history)

        # ✅ FIX: assign unique vuln_id
        if action.get("action_type") == "report_vulnerability":
            action["params"]["vuln_id"] = f"v{vuln_counter}"
            vuln_counter += 1

            key = action["params"]["name"] + action["params"]["location"]

            # prevent duplicates
            if key in reported:
                action = {"action_type": "request_hint", "params": {}}
            else:
                reported.add(key)

        # ✅ prevent early finalize
        if step < 3 and action.get("action_type") == "finalize":
            action = {"action_type": "request_hint", "params": {}}

        print("ACTION:", action)

        try:
            r = requests.post(
                f"{ENV_URL}/step",
                json=action,
                params={"task_id": task_id}
            )
            r.raise_for_status()
            result = r.json()

        except Exception as e:
            print("[STEP ERROR]", e)
            break

        obs = result["observation"]
        score = result["reward"]["score"]

        print(f"[STEP] {step+1} score={score:.4f}")

        history.append({
            "role": "assistant",
            "content": json.dumps(action)
        })

        if result["done"]:
            break

    print(f"[END] {task_id} score={score:.4f}")
    return score


# ================================
# MAIN
# ================================
def main():
    test_llm()

    scores = []
    for t in ["task1", "task2", "task3"]:
        scores.append(run_task(t))

    print("\nAverage:", sum(scores)/len(scores))


if __name__ == "__main__":
    main()