"""
Inference Script — SolidityGuard-Env
=====================================
MANDATORY
- API_BASE_URL, MODEL_NAME, HF_TOKEN must be set as environment variables
- Uses OpenAI Client for all LLM calls
- Stdout logs follow START/STEP/END structured format
"""

import os
import json
import requests
from openai import OpenAI

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or "dummy-key"
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
ENV_URL = os.getenv("ENV_URL", "http://localhost:7860")
MAX_STEPS = 15

try:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
except Exception as e:
    print(f"Warning: OpenAI client init failed: {e}")
    client = None

SYSTEM_PROMPT = """You are an expert smart contract security auditor. You will be given a Solidity contract and must find all security vulnerabilities.

For each vulnerability you find, use the report_vulnerability action.
After reporting vulnerabilities, use suggest_patch to propose fixes.
When done, use the finalize action.

You MUST respond with ONLY a valid JSON action. Available actions:

1. Report a vulnerability:
{"action_type": "report_vulnerability", "params": {"name": "Reentrancy", "severity": "critical", "location": "withdraw", "description": "External call before state update allows recursive reentry"}}

2. Suggest a patch:
{"action_type": "suggest_patch", "params": {"vuln_id": "REENTRANCY-001", "patch": "Apply checks-effects-interactions pattern: update balances[msg.sender] before making the external call"}}

3. Request a hint (costs -0.1 score):
{"action_type": "request_hint", "params": {}}

4. Finalize the audit:
{"action_type": "finalize", "params": {}}

5. No-op:
{"action_type": "noop", "params": {}}

Severity levels: critical, high, medium, low
Common vulnerabilities: Reentrancy, Integer Overflow/Underflow, Access Control, tx.origin Auth, Oracle Manipulation, Flash Loan Attack, Rug Pull, Precision Loss

Respond with ONLY the JSON. No explanation. No markdown."""


def get_action(obs: dict, history: list) -> dict:
    if client is None:
        return {"action_type": "noop", "params": {}}

    context = {
        "contract_name": obs["contract_name"],
        "task_description": obs["task_description"],
        "source_code": obs["source_code"],
        "known_findings": obs["known_findings"],
        "step": obs["step_number"],
        "hints_used": obs["hints_used"],
    }

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-6:]:
        messages.append(h)
    messages.append({
        "role": "user",
        "content": f"Contract to audit:\n\n{json.dumps(context, indent=2)}\n\nWhat is your next action?"
    })

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=300,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        action = json.loads(raw)
    except Exception as e:
        print(f"  [WARN] LLM call failed: {e} — using noop")
        action = {"action_type": "noop", "params": {}}
    return action


def run_task(task_id: str) -> float:
    print(f"[START] {task_id}")

    try:
        resp = requests.post(f"{ENV_URL}/reset", params={"task_id": task_id}, timeout=30)
        resp.raise_for_status()
        obs = resp.json()
    except Exception as e:
        print(f"[END] {task_id} score=0.0 error={e}")
        return 0.0

    history = []
    final_score = 0.0

    for step_num in range(MAX_STEPS):
        try:
            action = get_action(obs, history)
            atype = action.get("action_type", "noop")

            resp = requests.post(
                f"{ENV_URL}/step",
                json=action,
                params={"task_id": task_id},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            obs = result["observation"]
            reward = result["reward"]
            done = result["done"]
            final_score = reward["score"]

            print(f"[STEP] task={task_id} step={step_num+1} action={atype} score={final_score:.4f}")

            history.append({"role": "assistant", "content": json.dumps(action)})
            history.append({
                "role": "user",
                "content": f"Action result: {result['info'].get('message', '')} | score={final_score:.4f}"
            })

            if done:
                break
        except Exception as e:
            print(f"[STEP] task={task_id} step={step_num+1} action=error score={final_score:.4f} error={e}")
            break

    print(f"[END] {task_id} score={final_score:.4f}")
    return final_score


def main():
    scores = {}
    for task_id in ["task1", "task2", "task3"]:
        try:
            scores[task_id] = run_task(task_id)
        except Exception as e:
            print(f"[END] {task_id} score=0.0 error={e}")
            scores[task_id] = 0.0

    print("\n[RESULTS]")
    for tid, score in scores.items():
        print(f"  {tid}: {score:.4f}")
    avg = sum(scores.values()) / len(scores)
    print(f"  average: {avg:.4f}")


if __name__ == "__main__":
    main()
