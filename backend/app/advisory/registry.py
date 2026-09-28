from app.advisory.agents import Agent, BudgetAgent, DebtAgent, EmergencyAgent


class AgentRegistry:
    def __init__(self, agents: list[Agent]):
        self._agents = {agent.agent_id: agent for agent in agents}
        if len(self._agents) != len(agents):
            raise ValueError("Agent IDs must be unique.")

    @classmethod
    def default(cls) -> "AgentRegistry":
        return cls([BudgetAgent(), DebtAgent(), EmergencyAgent()])

    def get(self, agent_id: str) -> Agent:
        return self._agents[agent_id]
