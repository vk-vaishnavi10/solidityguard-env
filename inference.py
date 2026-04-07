"""
Inference Script — SolidityGuard-Env
=====================================
MANDATORY
- Before submitting, ensure the following variables are defined:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

- Named `inference.py`, placed in the root directory.
- Uses OpenAI Client for all LLM calls.
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
    print(f"\n{'='*60}")
    print(f"  TASK: {task_id.upper()}")
    print("="*60)

    try:
        resp = requests.post(f"{ENV_URL}/reset", params={"task_id": task_id}, timeout=30)
        resp.raise_for_status()
        obs = resp.json()
    except Exception as e:
        print(f"  ERROR resetting task: {e}")
        return 0.0

    print(f"  Contract : {obs['contract_name']}")
    print(f"  Task     : {obs['task_description'][:100]}...")

    history = []
    final_score = 0.0

    for step_num in range(MAX_STEPS):
        try:
            action = get_action(obs, history)
            atype = action.get("action_type", "?")
            aparams = action.get("params", {})
            print(f"\n  Step {step_num+1:02d} | {atype}")

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

            print(f"         reward={reward['score']:.4f} | vulns={reward['vulns_found']}/{reward['vulns_total']} | patches={reward['patches_correct']}")

            history.append({"role": "assistant", "content": json.dumps(action)})
            history.append({
                "role": "user",
                "content": f"Action result: {result['info'].get('message', '')} | score={reward['score']:.4f}"
            })

            if done:
                break
        except Exception as e:
            print(f"  ERROR on step {step_num+1}: {e}")
            break

    print(f"\n  Final score for {task_id}: {final_score:.4f}")
    return final_score


def main():
    scores = {}
    for task_id in ["task1", "task2", "task3"]:
        try:
            scores[task_id] = run_task(task_id)
        except Exception as e:
            print(f"\n  ERROR on {task_id}: {e}")
            scores[task_id] = 0.0

    print("\n" + "="*60)
    print("  BASELINE RESULTS — SolidityGuard-Env")
    print("="*60)
    for tid, score in scores.items():
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        print(f"  {tid}  [{bar}]  {score:.4f}")
    avg = sum(scores.values()) / len(scores)
    print(f"\n  Average: {avg:.4f}")
    print("="*60)


if __name__ == "__main__":
    main()