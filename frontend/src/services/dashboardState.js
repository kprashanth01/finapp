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
  const findings = (primary.source_refs ?? []).flatMap((ref) => {
    const agent = (session.result.agent_results ?? []).find((item) => item.agent_id === ref.agent_id)
    return agent?.findings?.filter((item) => item.code === ref.finding_code) ?? []
  })
  const evidence = findings.flatMap((finding) => finding.evidence ?? []).find((item) => item.value != null) ?? null
  const guidance = findings.find((finding) => finding.impact && finding.suggested_action)

  return { primary, evidence, impact: guidance?.impact ?? null, suggestedAction: guidance?.suggested_action ?? null,
    hasPriority: actions.length > 0, otherPriorities: actions.slice(1), plan }
}
