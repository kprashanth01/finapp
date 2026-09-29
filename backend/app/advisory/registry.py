from app.advisory.agents import Agent, BudgetAgent, DebtAgent, EmergencyAgent
from app.advisory.goal_agent import GoalPlanningAgent
from app.advisory.risk_agent import RiskAssessmentAgent
from app.advisory.investment_agent import InvestmentAgent


class AgentRegistry:
    def __init__(self, agents: list[Agent]):
        self._agents = {agent.agent_id: agent for agent in agents}
        if len(self._agents) != len(agents):
            raise ValueError("Agent IDs must be unique.")

    @classmethod
    def default(cls) -> "AgentRegistry":
        return cls([BudgetAgent(), DebtAgent(), EmergencyAgent(), GoalPlanningAgent(), RiskAssessmentAgent(), InvestmentAgent()])

    @property
    def agent_ids(self) -> tuple[str, ...]:
        return tuple(self._agents)

    def get(self, agent_id: str) -> Agent:
        return self._agents[agent_id]
