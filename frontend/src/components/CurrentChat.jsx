import { useRef, useState } from 'react'
import { askCurrentChat, explainApiError } from '../services/api.js'

const prompts = [
  'What should I prioritize?',
  'Why should I save before investing?',
  'Can I afford an upcoming expense?',
]

export default function CurrentChat({ userId }) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState('')
  const askingRef = useRef(false)

  async function ask(value) {
    const trimmed = value.trim()
    if (askingRef.current || trimmed.length < 3) return
    askingRef.current = true
    setAsking(true)
    setError('')
    try {
      const history = messages.slice(-6).map((item) => ({ question: item.question, answer: item.response.answer }))
      const response = await askCurrentChat(userId, trimmed, history)
      setMessages((current) => [...current, { question: trimmed, response }])
      setQuestion('')
    } catch (requestError) { setError(explainApiError(requestError)) }
    finally { askingRef.current = false; setAsking(false) }
  }

  return <section aria-labelledby="current-chat-heading" className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
    <h3 id="current-chat-heading" className="text-xl font-semibold">Ask about your current finances</h3>
    <p className="mt-1 text-sm text-slate-600">Ask about your saved picture and ranked actions. The local AI model explains recorded facts when available; otherwise you get a current, rule-based answer. Questions and answers are not saved.</p>
    <div className="mt-4 flex flex-wrap gap-2" aria-label="Suggested questions">
      {prompts.map((prompt) => <button key={prompt} type="button" disabled={asking} onClick={() => ask(prompt)}
        className="rounded-full border border-slate-300 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-50 disabled:opacity-50">{prompt}</button>)}
    </div>
    {messages.length > 0 && <ol className="mt-5 space-y-4" aria-label="Questions and answers" aria-live="polite">
      {messages.map((item, index) => <li key={index} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <p className="text-sm font-medium">You: {item.question}</p>
        <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{item.response.source === 'llm' ? 'Local AI explanation' : 'Current financial picture'} · {item.response.as_of_date}</p>
        <p className="mt-2 text-sm text-slate-800">{item.response.answer}</p>
        {item.response.fallback_reason && <p className="mt-2 text-xs text-slate-600">{item.response.fallback_reason === 'not_configured'
          ? 'The local AI model is unavailable, so this answer uses the current app calculations and ranked actions.'
          : 'The local AI response could not be verified, so this answer uses the current app calculations and ranked actions.'}</p>}
        {item.response.evidence.length > 0 && <details className="mt-3 text-sm"><summary className="cursor-pointer font-medium">See saved facts and actions used</summary>
          <ul className="mt-2 list-disc space-y-2 pl-5">{item.response.evidence.map((fact) => <li key={fact.id}><span className="font-medium">{fact.label}:</span> {fact.detail}</li>)}</ul>
        </details>}
      </li>)}
    </ol>}
    <form className="mt-5" onSubmit={(event) => { event.preventDefault(); ask(question) }}>
      <label htmlFor="current-chat-question" className="text-sm font-medium">Your question</label>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row"><input id="current-chat-question" value={question} maxLength={500}
        onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about your current finances" disabled={asking}
        className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-base disabled:bg-slate-100" />
        <button type="submit" disabled={asking || question.trim().length < 3}
          className="rounded-lg bg-slate-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50">{asking ? 'Answering…' : 'Ask'}</button></div>
    </form>
    {error && <p role="alert" className="mt-3 text-sm text-rose-800">{error}</p>}
  </section>
}
