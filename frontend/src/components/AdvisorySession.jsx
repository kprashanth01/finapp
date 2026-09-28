const agentNames = { budget: 'Budget', debt: 'Debt', emergency: 'Emergency fund' }

function formatEvidence(item) {
  if (item.value == null) return `${item.label}: unavailable`
  if (item.unit === '%') return `${item.label}: ${item.value}%`
  if (item.unit === 'months') return `${item.label}: ${item.value} months`
  return `${item.label}: ${item.value} (profile currency)`
}

function EvidenceList({ items }) {
  return (
    <ul className="mt-3 flex flex-wrap gap-2" aria-label="Supporting numbers">
      {items.map((item) => (
        <li key={item.label} className="rounded-md bg-slate-100 px-2.5 py-1 text-xs text-slate-700">
          {formatEvidence(item)}
        </li>
      ))}
    </ul>
  )
}

function AdvisorySession({ session, loading, running, saving, error, onRun }) {
  const result = session?.result
  const agents = Object.fromEntries((result?.agent_results ?? []).map((item) => [item.agent_id, item]))

  return (
    <section className="mt-10 border-t border-slate-200 pt-8" aria-labelledby="advisory-heading">
      <h2 id="advisory-heading" className="text-xl font-semibold">4. Advisory session</h2>
      <p className="mt-1 text-sm text-slate-600">
        Run three transparent rule-based checks on your saved profile. The findings are educational project outputs, not validated financial advice. Displayed ratios are rounded; rules compare the saved amounts.
      </p>

      <button
        type="button"
        onClick={onRun}
        disabled={running || loading || saving}
        className="mt-5 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
      >
        {running ? 'Running…' : session ? 'Run analysis again' : 'Run analysis'}
      </button>

      {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      {loading && <p className="mt-4 text-sm text-slate-600">Loading latest saved session…</p>}
      {!loading && !session && <p className="mt-4 text-sm text-slate-600">No advisory session has been run yet.</p>}

      {session && (
        <div className="mt-6 space-y-5">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
            <p className="font-medium">Saved run #{session.id}</p>
            <p className="mt-1 text-slate-600">{new Date(session.created_at).toLocaleString()} · Rule-based method · {session.rule_version}</p>
            {session.is_stale && (
              <p className="mt-3 rounded-md bg-amber-50 p-3 text-amber-900">
                Your saved financial inputs have changed since this run. These findings still show the earlier inputs. Run analysis again to update them.
              </p>
            )}
          </div>

          <div>
            <h3 className="text-base font-semibold">Priority findings</h3>
            {result.priority_actions.length === 0 ? (
              <p className="mt-2 text-sm text-slate-600">No priority finding was produced by the current rules. Check the agent details below for available and missing inputs.</p>
            ) : (
              <ol className="mt-3 space-y-3">
                {result.priority_actions.map((action) => (
                  <li key={action.code} className="rounded-lg border border-slate-200 p-4">
                    <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{agentNames[action.agent_id]} check</p>
                    <h4 className="mt-1 font-semibold">{action.title}</h4>
                    <p className="mt-1 text-sm text-slate-700">{action.reason}</p>
                    <EvidenceList items={action.evidence} />
                    {action.limitations.map((limit) => <p key={limit} className="mt-2 text-xs text-slate-500">{limit}</p>)}
                  </li>
                ))}
              </ol>
            )}
          </div>

          <details className="rounded-lg border border-slate-200 p-4">
            <summary className="cursor-pointer text-sm font-medium">How agents were selected and what they found</summary>
            <div className="mt-4 space-y-4">
              {result.decision.selections.map((selection) => {
                const agent = agents[selection.agent_id]
                return (
                  <div key={selection.agent_id} className="border-t border-slate-100 pt-3 first:border-t-0 first:pt-0">
                    <h4 className="font-medium">{agentNames[selection.agent_id]} · {selection.selected ? 'selected' : 'skipped'}</h4>
                    <p className="mt-1 text-sm text-slate-600">{selection.reason}</p>
                    {agent && (
                      <>
                        {agent.findings.map((finding) => (
                          <div key={finding.code} className="mt-2 text-sm">
                            <p>{finding.title}: {finding.reason}</p>
                            <EvidenceList items={finding.evidence} />
                          </div>
                        ))}
                        {agent.limitations.map((limit) => <p key={limit} className="mt-2 text-xs text-slate-500">{limit}</p>)}
                      </>
                    )}
                  </div>
                )
              })}
            </div>
          </details>
        </div>
      )}
    </section>
  )
}

export default AdvisorySession
