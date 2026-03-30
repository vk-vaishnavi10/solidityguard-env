# SolidityGuard-Env 🛡️

[![openenv](https://img.shields.io/badge/openenv-compatible-green)](https://openenv.dev)
[![domain](https://img.shields.io/badge/domain-smart--contracts-blue)]()
[![difficulty](https://img.shields.io/badge/tasks-easy%20→%20hard-orange)]()

> **The first OpenEnv environment for smart contract security auditing.**
> An AI agent reads vulnerable Solidity contracts, identifies security flaws, classifies severity, and proposes patches — exactly what a human auditor does before a protocol goes live.

---

## Why This Matters

Smart contract vulnerabilities have caused **over $3 billion in losses** — The DAO hack, Ronin Bridge, Euler Finance. Every contract needs a security audit before deployment. This environment trains and benchmarks AI agents to perform that audit automatically.

---

## Environment Overview

The agent receives a Solidity contract and must:
1. **Detect** vulnerabilities (reentrancy, access control, oracle manipulation, etc.)
2. **Classify** severity: `critical` / `high` / `medium` / `low`
3. **Locate** the vulnerable function
4. **Patch** — suggest a concrete fix

---

## Action Space

| Action | Params | Description |
|--------|--------|-------------|
| `report_vulnerability` | `name`, `severity`, `location`, `description` | Submit a found vulnerability |
| `suggest_patch` | `vuln_id`, `patch` | Propose a fix for a vulnerability |
| `request_hint` | none | Get a hint (−0.1 score penalty) |
| `finalize` | none | Declare audit complete (+0.05 bonus) |
| `noop` | none | Do nothing |

## Observation Space

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | str | Current task identifier |
| `task_description` | str | What the agent must do |
| `contract_name` | str | Name of the Solidity contract |
| `source_code` | str | Full Solidity source |
| `abi_summary` | list | Function signatures |
| `known_findings` | list | Vulnerabilities reported so far |
| `step_number` | int | Current step |
| `done` | bool | Episode over? |
| `hints_used` | int | Hints consumed |

---

## Tasks

### Task 1 — Easy: `SimpleBank` (1 vulnerability)
- **Contract**: A minimal ETH bank with deposit/withdraw
- **Vuln**: Classic reentrancy in `withdraw()` — state updated after external call
- **Inspiration**: The DAO hack, 2016 ($60M lost)

### Task 2 — Medium: `VaultManager` (3 vulnerabilities)
- **Contract**: Multi-user ETH vault with pause mechanism
- **Vulns**: `tx.origin` authentication flaw, reentrancy in `withdraw()`, missing access control on `emergencyDrain()`
- **Challenge**: Must find all three with correct severity classification

### Task 3 — Hard: `LendingPool` (4 vulnerabilities)
- **Contract**: DeFi lending pool with ERC-20 tokens, flash loans, collateral
- **Vulns**: Flash loan reentrancy, integer precision loss in interest calculation, price oracle manipulation, admin rug pull (no timelock)
- **Challenge**: Find all 4 AND suggest correct patches for each

---

## Reward Function

```
score = detection(0.60) + patch(0.35) + finalize_bonus(0.05)
      - hint_penalty(0.10 each)
      - false_positive_penalty(0.05 each)
```

- **Detection**: keyword + severity + location matching against ground truth
- **Patch**: patch text matched against accepted fix patterns
- **Partial credit**: incorrect severity = 0.5× detection score
- **Score range**: 0.0 – 1.0

---

## Setup

### Local
```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 7860
```

### Docker
```bash
docker build -t solidityguard-env .
docker run -p 7860:7860 solidityguard-env
```

### API Usage
```bash
# Reset task
curl -X POST "http://localhost:7860/reset?task_id=task1"

# Report a vulnerability
curl -X POST "http://localhost:7860/step?task_id=task1" \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "report_vulnerability",
    "params": {
      "name": "Reentrancy",
      "severity": "critical",
      "location": "withdraw",
      "description": "External call before state update allows recursive reentry"
    }
  }'

# Suggest a patch
curl -X POST "http://localhost:7860/step?task_id=task1" \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "suggest_patch",
    "params": {
      "vuln_id": "REENTRANCY-001",
      "patch": "Apply checks-effects-interactions: update balances before calling msg.sender"
    }
  }'
```

---

## Running the Baseline

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="meta-llama/Llama-3.3-70B-Instruct"
export HF_TOKEN="your_token_here"
export ENV_URL="http://localhost:7860"

python inference.py
```

### Baseline Scores

| Task | Contract | Vulns | Difficulty | Baseline |
|------|----------|-------|-----------|----------|
| task1 | SimpleBank | 1 | Easy | ~0.82 |
| task2 | VaultManager | 3 | Medium | ~0.61 |
| task3 | LendingPool | 4 | Hard | ~0.40 |

---

## Project Structure

```
solidityguard-env/
├── Dockerfile
├── openenv.yaml
├── inference.py          ← mandatory baseline script
├── requirements.txt
├── README.md
├── app.py                ← FastAPI server
└── env/
    ├── __init__.py
    ├── models.py         ← Pydantic: Observation, Action, Reward
    ├── contracts.py      ← Solidity contracts + ground truth
    ├── grader.py         ← Deterministic scoring logic
    └── environment.py    ← reset() / step() / state()
```

---

## Team

**MindBloom** — Built for OpenEnv Hackathon Round 1

*Cybersecurity × Blockchain × AI agents*