import { useState } from 'react'
import { explainApiError, explainLiveRun, explainSavedSession } from '../services/api.js'

const labels = [
  ['financial_overview', 'Financial overview'],
  ['agent_analysis', 'Agent analysis'],
  ['orchestration_decision', 'Orchestration decision'],
  ['final_recommendation', 'Final recommendation'],
  ['why_this_recommendation', 'Why this recommendation?'],
  ['limitations', 'Limitations'],
]

const fallbackMessages = {
  not_configured: 'The model is not configured on this server. This explanation uses the saved deterministic evidence.',
  provider_error: 'The model could not be reached. This explanation uses the saved deterministic evidence.',
  invalid_output: 'The model output did not pass validation. This explanation uses the saved deterministic evidence.',
}

export default function ReasoningPanel({ userId, sessionId, liveResult }) {
  const [explanation, setExplanation] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function generate() {
    if (loading) return
    setLoading(true); setError(''); setExplanation(null)
    try {
      const response = sessionId == null
        ? await explainLiveRun(userId, liveResult)
        : await explainSavedSession(userId, sessionId)
      setExplanation(response)
    } catch (requestError) { setError(explainApiError(requestError)) }
    finally { setLoading(false) }
  }

  const evidence = Object.fromEntries((explanation?.evidence ?? []).map((item) => [item.id, item]))
  return <section className="reasoning-panel" aria-label="Explanation of this run">
    <div className="reasoning-panel-head">
      <div><h3>Explain this run</h3></div>
      <button type="button" className="primary-action" onClick={generate} disabled={loading}>{loading ? 'Generating…' : explanation ? 'Generate again' : 'Generate explanation'}</button>
    </div>
    <p>The financial amounts, agent findings and recommendation for this run are sent to OpenAI only if a model is configured and you press the button. Account name and email fields are excluded. The response is not saved to history.</p>
    {error && <p role="alert" className="research-error">{error}</p>}
    {explanation && <div aria-live="polite">
      <p className="reasoning-source">{explanation.source === 'llm' ? `AI-written synthesis · ${explanation.model}` : 'Deterministic explanation'}</p>
      {explanation.fallback_reason && <p className="reasoning-fallback">{fallbackMessages[explanation.fallback_reason]}</p>}
      <div className="reasoning-sections">{labels.map(([key, title]) => {
        const section = explanation.sections[key]
        return <section key={key}><h4>{title}</h4><p>{section.text}</p>
          <ul className="reasoning-evidence">{section.evidence_ids.map((id) => <li key={id}><strong>{evidence[id]?.label}</strong><span>{evidence[id]?.detail}</span></li>)}</ul>
        </section>
      })}</div>
    </div>}
    <p className="reasoning-disclaimer">This system provides educational financial guidance based on the information provided and is not a substitute for professional financial advice.</p>
  </section>
}
