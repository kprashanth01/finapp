export function getDashboardDisplayState({ saving = false, analysis = null, advisoryLoading = false, advisoryError = '', advisorySession = null }) {
  return {
    updating: saving,
    snapshot: analysis ? 'ready' : 'unavailable',
    latest: advisoryLoading ? 'loading' : advisoryError ? 'error' : advisorySession ? 'saved' : 'empty',
  }
}

export function getDashboardDecision(session) {
  if (!session || session.is_stale || !session.result?.advice) return null

  const { summary, monthly_plan: plan, priority_actions: actions = [] } = session.result.advice
  const primary = actions[0] ?? { ...summary, reason: summary.text }
  const evidence = (primary.source_refs ?? []).flatMap((ref) => {
    const agent = (session.result.agent_results ?? []).find((item) => item.agent_id === ref.agent_id)
    const finding = agent?.findings.find((item) => item.code === ref.finding_code)
    return finding?.evidence ?? []
  }).find((item) => item.value != null) ?? null

  return { primary, evidence, hasPriority: actions.length > 0, otherPriorities: actions.slice(1), plan }
}
