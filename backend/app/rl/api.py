"""Authenticated, read-only policy comparison on the owner's saved profile."""

from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisory.service import financial_state, planning_date
from app.auth_dependencies import require_owner
from app.database import get_session
from app.goal_api import load_active_goals
from app.models import FinancialProfile, User
from app.rl.environment import AgentSelectionEnv
from app.rl.observation import FEATURE_NAMES, OBSERVATION_VERSION
from app.rl.policy import FittedQPolicy, POLICY_VERSION
from app.rl.reward import REWARD_VERSION
from app.rl.selection import ACTION_COUNT, ACTION_VERSION, rule_action


router = APIRouter()
MODEL_PATH = Path(__file__).with_name("model.json")


class ComparisonRequest(BaseModel):
    seed: int = Field(default=42, ge=0, le=1_000_000_000)


def _outcome(state, action):
    environment = AgentSelectionEnv(state)
    environment.reset()
    _, reward, _, _, info = environment.step(action)
    return {
        "action": int(action),
        "selected_agents": info["selected_agents"],
        "total_reward": reward,
        "reward_components": info["reward_components"],
        "findings": [
            {"agent_id": result["agent_id"], "title": finding["title"],
             "reason": finding["reason"], "priority": finding["priority"]}
            for result in info["agent_results"] for finding in result["findings"]
        ],
    }


@router.post("/users/{user_id}/research/comparison", dependencies=[Depends(require_owner)])
def compare_policies(user_id: int, payload: ComparisonRequest,
                     session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    profile = session.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Financial profile not found.")
    state = financial_state(user, profile, load_active_goals(session, user_id), planning_date())
    environment = AgentSelectionEnv(state)
    observation, _ = environment.reset(seed=payload.seed)
    random_action = int(np.random.default_rng(payload.seed).integers(ACTION_COUNT))
    policies = {
        "rule": _outcome(state, rule_action(state)),
        "random": _outcome(state, random_action),
    }
    try:
        model = FittedQPolicy.load(MODEL_PATH)
    except (OSError, ValueError, KeyError, TypeError):
        model_status = {"status": "unavailable", "reason": "No compatible trained model is installed."}
    else:
        policies["learned"] = _outcome(state, model.predict_action(observation))
        model_status = {
            "status": "available", "policy_version": POLICY_VERSION,
            "training": model.training,
        }
    return {
        "source": "saved_profile",
        "seed": payload.seed,
        "as_of_date": state.as_of_date.isoformat(),
        "state_fingerprint": state.fingerprint(),
        "observation_version": OBSERVATION_VERSION,
        "action_version": ACTION_VERSION,
        "reward_version": REWARD_VERSION,
        "feature_names": FEATURE_NAMES,
        "observation": observation.tolist(),
        "model": model_status,
        "policies": policies,
    }
