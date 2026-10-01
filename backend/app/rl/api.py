"""Authenticated, read-only policy comparison on the owner's saved profile."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisory.service import financial_state, planning_date
from app.advisory.planning_types import ExplanationTrace
from app.advisory.reasoning import ReasoningResponse, explain_run
from app.auth_dependencies import require_owner
from app.database import get_session
from app.goal_api import load_active_goals
from app.models import FinancialProfile, User
from app.rl.baselines import RandomBaseline, RuleBaseline
from app.rl.dqn_artifact import DEFAULT_ARTIFACT_DIR, read_training_evidence
from app.rl.environment import AgentSelectionEnv
from app.rl.evaluation import read_evaluation_report
from app.rl.evaluation_dashboard import latest_measurements
from app.rl.observation import FEATURE_NAMES, OBSERVATION_VERSION
from app.rl.orchestration import (InvalidOrchestratorModeError, ModelUnavailableError,
                                  run_orchestration)
from app.rl.policy import FittedQPolicy, POLICY_VERSION
from app.rl.reward import REWARD_VERSION
from app.rl.selection import ACTION_VERSION, DEFAULT_CATALOG


router = APIRouter()
MODEL_PATH = Path(__file__).with_name("model.json")
DQN_ARTIFACT_DIR = DEFAULT_ARTIFACT_DIR
EVALUATION_REPORT_PATH = DEFAULT_ARTIFACT_DIR / "evaluation_report.json"


class ComparisonRequest(BaseModel):
    seed: int = Field(default=42, ge=0, le=1_000_000_000)


class ManualActionRequest(BaseModel):
    selected_agents: list[str] = Field(min_length=1, max_length=6)


class OrchestrationRunRequest(BaseModel):
    mode: Literal["rule_based", "random", "trained_rl", "rl"] | None = None
    seed: int = Field(default=42, ge=0, le=1_000_000_000)


class OrchestrationReasoningRequest(OrchestrationRunRequest):
    mode: Literal["rule_based", "random", "trained_rl", "rl"]
    state_fingerprint: str = Field(min_length=64, max_length=64)
    action: int = Field(ge=0)


def _saved_state(user_id: int, session: Session):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    profile = session.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Financial profile not found.")
    return financial_state(user, profile, load_active_goals(session, user_id), planning_date())


def _outcome(state, action, *, include_agent_results=False):
    environment = AgentSelectionEnv(state)
    environment.reset()
    _, reward, _, _, info = environment.step(action)
    outcome = {
        "action": int(action),
        "selected_agents": info["selected_agents"],
        "total_reward": reward,
        "reward_components": info["reward_components"],
        "reward_audit": info["reward_audit"],
        "plan_readiness": info["plan_readiness"],
        "findings": [
            {"agent_id": result["agent_id"], "title": finding["title"],
             "reason": finding["reason"], "priority": finding["priority"]}
            for result in info["agent_results"] for finding in result["findings"]
        ],
    }
    if include_agent_results:
        outcome["agent_results"] = info["agent_results"]
    return outcome


@router.get("/users/{user_id}/research/actions", dependencies=[Depends(require_owner)])
def list_research_actions(user_id: int, session: Session = Depends(get_session)):
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return DEFAULT_CATALOG.describe()


@router.get("/users/{user_id}/research/monthly-demo", dependencies=[Depends(require_owner)])
def get_monthly_demo(user_id: int, session: Session = Depends(get_session)):
    """Expose a reproducible synthetic monthly case, not the owner's profile."""
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    from app.rl.monthly_demo import build_monthly_demo

    try:
        return build_monthly_demo()
    except (OSError, ValueError, ImportError) as error:
        raise HTTPException(status_code=503, detail=f"Monthly demo unavailable: {error}") from error


@router.get("/users/{user_id}/research/training-evidence", dependencies=[Depends(require_owner)])
def get_training_evidence(user_id: int, session: Session = Depends(get_session)):
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return read_training_evidence(DQN_ARTIFACT_DIR)


@router.get("/users/{user_id}/research/evaluation", dependencies=[Depends(require_owner)])
def get_research_evaluation(user_id: int, session: Session = Depends(get_session)):
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return read_evaluation_report(EVALUATION_REPORT_PATH)


@router.get("/users/{user_id}/research/experiments/latest/metrics", dependencies=[Depends(require_owner)])
def get_research_measurements(user_id: int, method: str | None = Query(default=None, max_length=40),
                              scenario: str | None = Query(default=None, max_length=80),
                              metric: str | None = Query(default=None, max_length=80),
                              scope: Literal["aggregate", "seed"] = "aggregate",
                              session: Session = Depends(get_session)):
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return latest_measurements(session, method=method, scenario=scenario, metric=metric, scope=scope)


@router.post("/users/{user_id}/research/orchestration-run", dependencies=[Depends(require_owner)])
def run_policy_on_saved_profile(user_id: int, payload: OrchestrationRunRequest,
                                session: Session = Depends(get_session)):
    state = _saved_state(user_id, session)
    try:
        return run_orchestration(state, mode=payload.mode, seed=payload.seed)
    except (InvalidOrchestratorModeError, ModelUnavailableError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post('/users/{user_id}/research/orchestration-reasoning',
             response_model=ReasoningResponse, dependencies=[Depends(require_owner)])
def explain_live_orchestration(user_id: int, payload: OrchestrationReasoningRequest,
                               session: Session = Depends(get_session)) -> ReasoningResponse:
    state = _saved_state(user_id, session)
    if state.fingerprint() != payload.state_fingerprint:
        raise HTTPException(status_code=409, detail='The saved profile changed. Run the selection again.')
    try:
        result = run_orchestration(state, mode=payload.mode, seed=payload.seed)
    except (InvalidOrchestratorModeError, ModelUnavailableError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if result['action'] != payload.action:
        raise HTTPException(status_code=409, detail='The selected action changed. Run the selection again.')
    return explain_run(ExplanationTrace.model_validate(result['explanation']),
                       result['summary'], result['agent_results'])


@router.post("/users/{user_id}/research/manual-action", dependencies=[Depends(require_owner)])
def run_manual_action(user_id: int, payload: ManualActionRequest,
                      session: Session = Depends(get_session)):
    state = _saved_state(user_id, session)
    try:
        action = DEFAULT_CATALOG.action_for(payload.selected_agents)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "source": "saved_profile",
        "as_of_date": state.as_of_date.isoformat(),
        "state_fingerprint": state.fingerprint(),
        "action_version": DEFAULT_CATALOG.version,
        "recommendation_generated": False,
        **_outcome(state, action, include_agent_results=True),
    }


@router.post("/users/{user_id}/research/comparison", dependencies=[Depends(require_owner)])
def compare_policies(user_id: int, payload: ComparisonRequest,
                     session: Session = Depends(get_session)):
    state = _saved_state(user_id, session)
    environment = AgentSelectionEnv(state)
    observation, _ = environment.reset(seed=payload.seed)
    rule_action = RuleBaseline().choose_action(state, environment.catalog)
    random_action = RandomBaseline(seed=payload.seed).choose_action(state, environment.catalog)
    policies = {
        "rule": _outcome(state, rule_action),
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
