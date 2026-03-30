from typing import Any, Dict, List, Optional, Tuple

from env.contracts import TASKS
from env.grader import grade
from env.models import Action, Observation, Reward


HINTS = {
    "task1": [
        "Look at the order of operations in withdraw() — when is the balance updated?",
        "Search for the pattern: external call → state change. It should be reversed.",
    ],
    "task2": [
        "Check every authentication mechanism — is msg.sender always safe to use?",
        "Look for functions with no modifiers at all — should they be public?",
        "Count the vulnerabilities — there are three.",
    ],
    "task3": [
        "Flash loans + arbitrary callbacks are a classic reentrancy vector.",
        "Check the interest calculation formula — order of operations matters in integer math.",
        "What is the price oracle for collateral? Is it manipulable?",
        "Can the admin change the token contract instantly? What's the risk?",
    ],
    "task4": [
        "Where does randomness come from? Can miners influence it?",
        "In whitelistMint — who actually receives the NFT? Is that intended?",
        "The contract takes ETH — can anyone ever get it out?",
    ],
    "task5": [
        "ERC-20 approve() has a well-known race condition — look it up.",
        "DOMAIN_SEPARATOR is set once in the constructor — what happens after a chain fork?",
        "Check every state-changing function — does each one verify the caller?",
        "Is the fee applied consistently across all transfer methods?",
    ],
}

MAX_STEPS = 30


class SolidityGuardEnv:

    def __init__(self, task_id: str = "task1"):
        assert task_id in TASKS, f"task_id must be one of {list(TASKS.keys())}"
        self.task_id = task_id
        self._task_data: Optional[Dict] = None
        self._findings: List[Dict] = []
        self._patches: Dict[str, str] = {}
        self._hints_used: int = 0
        self._hint_index: int = 0
        self._step_number: int = 0
        self._done: bool = False
        self._finalized: bool = False
        self._last_reward: float = 0.0

    # ── helpers ──────────────────────────────────────────────────────────────

    def _to_obs(self) -> Observation:
        return Observation(
            task_id=self.task_id,
            task_description=self._task_data["description"],
            contract_name=self._task_data["contract_name"],
            source_code=self._task_data["source_code"],
            abi_summary=self._task_data["abi_summary"],
            known_findings=self._findings.copy(),
            step_number=self._step_number,
            done=self._done,
            hints_used=self._hints_used,
        )

    def _compute_reward(self) -> Reward:
        result = grade(
            task_data=self._task_data,
            findings=self._findings,
            patches=self._patches,
            hints_used=self._hints_used,
            finalized=self._finalized,
        )
        return Reward(**result)

    # ── OpenEnv API ──────────────────────────────────────────────────────────

    def reset(self) -> Observation:
        self._task_data = TASKS[self.task_id]
        self._findings = []
        self._patches = {}
        self._hints_used = 0
        self._hint_index = 0
        self._step_number = 0
        self._done = False
        self._finalized = False
        self._last_reward = 0.0
        return self._to_obs()

    def state(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "difficulty": self._task_data["difficulty"] if self._task_data else "unknown",
            "step_number": self._step_number,
            "done": self._done,
            "finalized": self._finalized,
            "findings_count": len(self._findings),
            "patches_count": len(self._patches),
            "hints_used": self._hints_used,
            "last_reward": self._last_reward,
        }

    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict]:
        if self._task_data is None:
            raise RuntimeError("Call reset() before step()")
        if self._done:
            return self._to_obs(), self._compute_reward(), True, {"message": "Episode already done"}

        self._step_number += 1
        info: Dict[str, Any] = {}

        try:
            info = self._apply_action(action)
            info["action_status"] = "success"
        except Exception as e:
            info["action_status"] = "error"
            info["error"] = str(e)

        reward = self._compute_reward()
        self._last_reward = reward.score

        # Done conditions
        if (
            self._finalized
            or reward.score >= 1.0
            or self._step_number >= MAX_STEPS
        ):
            self._done = True

        obs = self._to_obs()
        return obs, reward, self._done, info

    # ── action handlers ───────────────────────────────────────────────────────

    def _apply_action(self, action: Action) -> Dict:
        a = action.action_type
        p = action.params or {}

        if a == "report_vulnerability":
            required = ["name", "severity", "location", "description"]
            for field in required:
                if field not in p:
                    raise ValueError(f"report_vulnerability requires field: {field}")
            severity = p["severity"].lower()
            if severity not in ("critical", "high", "medium", "low"):
                raise ValueError("severity must be: critical / high / medium / low")
            # avoid duplicate submissions
            existing = [f["name"].lower() for f in self._findings]
            if p["name"].lower() not in existing:
                self._findings.append({
                    "name": p["name"],
                    "severity": severity,
                    "location": p["location"],
                    "description": p["description"],
                })
                return {"message": f"Vulnerability reported: {p['name']}"}
            return {"message": f"Duplicate finding skipped: {p['name']}"}

        elif a == "suggest_patch":
            vuln_id = p.get("vuln_id") or p.get("name", "")
            patch_text = p.get("patch", "") or p.get("description", "")
            if not patch_text:
                raise ValueError("suggest_patch requires 'patch' field")
            # match to a known vuln_id by name keyword
            gt_vulns = self._task_data["ground_truth"]["vulnerabilities"]
            matched_id = None
            for gt in gt_vulns:
                if gt["vuln_id"].lower() in vuln_id.lower() or any(
                    kw.lower() in vuln_id.lower() for kw in gt["keywords"][:3]
                ):
                    matched_id = gt["vuln_id"]
                    break
            if matched_id:
                self._patches[matched_id] = patch_text
                return {"message": f"Patch recorded for {matched_id}"}
            # store by provided key anyway
            self._patches[vuln_id] = patch_text
            return {"message": f"Patch recorded (unmatched key): {vuln_id}"}

        elif a == "request_hint":
            hints = HINTS.get(self.task_id, [])
            if self._hint_index < len(hints):
                hint = hints[self._hint_index]
                self._hint_index += 1
                self._hints_used += 1
                return {"hint": hint, "message": f"Hint {self._hints_used} used (-0.1 penalty)"}
            return {"message": "No more hints available"}

        elif a == "finalize":
            self._finalized = True
            return {"message": "Audit finalized"}

        elif a == "noop":
            return {"message": "No operation"}

        else:
            raise ValueError(f"Unknown action_type: {a}")