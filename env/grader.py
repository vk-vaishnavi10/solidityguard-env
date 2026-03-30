"""
Graders for SolidityGuard-Env.
All graders are deterministic and return scores in [0.0, 1.0].

Scoring philosophy:
  - Detection score:  did the agent find the vuln? (keyword + severity match)
  - Patch score:      did the agent suggest a correct fix?
  - Hint penalty:     -0.1 per hint used (capped at -0.3)
  - False positive:   -0.05 per spurious finding (capped at -0.2)
"""

from typing import Any, Dict, List


SEVERITY_WEIGHTS = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.6,
    "low": 0.3,
}


def _match_vuln(finding: Dict, ground: Dict) -> float:
    """
    Return a 0.0–1.0 match score between an agent finding and a ground-truth vuln.
    Checks: keyword overlap in name/description, severity match, location match.
    """
    keywords: List[str] = ground["keywords"]
    finding_text = (
        finding.get("name", "") + " " +
        finding.get("description", "") + " " +
        finding.get("location", "")
    ).lower()

    keyword_hits = sum(1 for kw in keywords if kw.lower() in finding_text)
    keyword_score = min(1.0, keyword_hits / max(1, len(keywords) * 0.4))  # need ~40% keyword hit

    severity_match = 1.0 if finding.get("severity", "").lower() == ground["severity"] else 0.5
    location_match = 1.0 if ground["location"].lower() in finding.get("location", "").lower() else 0.7

    return round(keyword_score * 0.6 + severity_match * 0.2 + location_match * 0.2, 4)


def _match_patch(patch_text: str, accepted: List[str]) -> float:
    patch_lower = patch_text.lower()
    hits = sum(1 for p in accepted if p.lower() in patch_lower)
    return min(1.0, hits / max(1, len(accepted) * 0.3))


def grade(
    task_data: Dict,
    findings: List[Dict],
    patches: Dict[str, str],
    hints_used: int,
    finalized: bool,
) -> Dict[str, Any]:
    ground_truth = task_data["ground_truth"]
    gt_vulns = ground_truth["vulnerabilities"]
    accepted_patches = ground_truth.get("accepted_patches", {})

    # ── 1. Detection score ──────────────────────────────────────────────────
    detection_scores = {}
    matched_findings = set()

    for gt in gt_vulns:
        best_score = 0.0
        best_idx = -1
        for i, finding in enumerate(findings):
            if i in matched_findings:
                continue
            s = _match_vuln(finding, gt)
            if s > best_score:
                best_score = s
                best_idx = i
        if best_idx >= 0 and best_score >= 0.4:
            matched_findings.add(best_idx)
            detection_scores[gt["vuln_id"]] = best_score
        else:
            detection_scores[gt["vuln_id"]] = 0.0

    detection_avg = sum(detection_scores.values()) / len(gt_vulns)

    # ── 2. Patch score ───────────────────────────────────────────────────────
    patch_scores = {}
    for vuln_id, accepted in accepted_patches.items():
        if vuln_id in patches:
            patch_scores[vuln_id] = _match_patch(patches[vuln_id], accepted)
        else:
            patch_scores[vuln_id] = 0.0

    patch_avg = sum(patch_scores.values()) / max(1, len(accepted_patches)) if accepted_patches else 1.0

    # ── 3. False positive penalty ────────────────────────────────────────────
    fp_count = max(0, len(findings) - len(matched_findings) - 1)  # allow 1 extra
    fp_penalty = min(0.2, fp_count * 0.05)

    # ── 4. Hint penalty ──────────────────────────────────────────────────────
    hint_penalty = min(0.3, hints_used * 0.1)

    # ── 5. Finalization bonus ─────────────────────────────────────────────────
    finalize_bonus = 0.05 if finalized else 0.0

    # ── 6. Weighted final score ───────────────────────────────────────────────
    # detection = 60%, patch = 35%, finalize bonus = 5%
    raw = detection_avg * 0.60 + patch_avg * 0.35 + finalize_bonus
    final = max(0.0, min(1.0, round(raw - fp_penalty - hint_penalty, 4)))

    vulns_found = sum(1 for s in detection_scores.values() if s >= 0.4)
    patches_correct = sum(1 for s in patch_scores.values() if s >= 0.5)

    return {
        "score": final,
        "partial_credits": {
            **{f"detect_{k}": round(v, 4) for k, v in detection_scores.items()},
            **{f"patch_{k}": round(v, 4) for k, v in patch_scores.items()},
            "fp_penalty": -round(fp_penalty, 4),
            "hint_penalty": -round(hint_penalty, 4),
        },
        "message": (
            f"Found {vulns_found}/{len(gt_vulns)} vulns | "
            f"{patches_correct} patches correct | "
            f"score={final}"
        ),
        "vulns_found": vulns_found,
        "vulns_total": len(gt_vulns),
        "patches_correct": patches_correct,
    }