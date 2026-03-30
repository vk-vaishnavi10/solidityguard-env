from fastapi import FastAPI, HTTPException
from typing import Dict
from env.environment import SolidityGuardEnv
from env.models import Action
from env.contracts import TASKS

app = FastAPI(
    title="SolidityGuard-Env",
    description="OpenEnv environment for smart contract security auditing agents.",
    version="1.0.0",
)

_envs: Dict[str, SolidityGuardEnv] = {
    tid: SolidityGuardEnv(tid) for tid in TASKS
}


@app.get("/")
def root():
    return {
        "status": "ok",
        "env": "solidityguard-env",
        "description": "Smart contract auditing environment for AI agents",
        "tasks": list(_envs.keys()),
    }


@app.post("/reset")
def reset(task_id: str = "task1"):
    if task_id not in _envs:
        raise HTTPException(404, f"Unknown task_id: {task_id}")
    obs = _envs[task_id].reset()
    return obs.model_dump()


@app.get("/state")
def state(task_id: str = "task1"):
    if task_id not in _envs:
        raise HTTPException(404, f"Unknown task_id: {task_id}")
    return _envs[task_id].state()


@app.post("/step")
def step(action: Action, task_id: str = "task1"):
    if task_id not in _envs:
        raise HTTPException(404, f"Unknown task_id: {task_id}")
    try:
        obs, reward, done, info = _envs[task_id].step(action)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {
        "observation": obs.model_dump(),
        "reward": reward.model_dump(),
        "done": done,
        "info": info,
    }


@app.get("/tasks")
def list_tasks():
    return {
        tid: {
            "difficulty": TASKS[tid]["difficulty"],
            "contract_name": TASKS[tid]["contract_name"],
            "total_vulns": TASKS[tid]["total_vulns"],
            "description": TASKS[tid]["description"],
        }
        for tid in TASKS
    }