from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class Vulnerability(BaseModel):
    vuln_id: str
    name: str
    severity: str          # critical / high / medium / low
    location: str          # function name or line hint
    description: str


class Observation(BaseModel):
    task_id: str
    task_description: str
    contract_name: str
    source_code: str
    abi_summary: List[Dict[str, Any]]   # function signatures
    known_findings: List[Dict[str, Any]]  # findings submitted so far
    step_number: int
    done: bool
    hints_used: int


class Action(BaseModel):
    action_type: str
    # action_types:
    #   report_vulnerability  — submit a found vulnerability
    #   suggest_patch         — suggest a fix for a vuln_id
    #   request_hint          — get a hint (costs 0.1 score penalty)
    #   finalize              — declare audit complete
    #   noop                  — do nothing
    params: Optional[Dict[str, Any]] = {}


class Reward(BaseModel):
    score: float                        # 0.0 – 1.0
    partial_credits: Dict[str, float]
    message: str
    vulns_found: int
    vulns_total: int
    patches_correct: int