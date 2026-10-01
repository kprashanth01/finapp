import { useRef, useState } from 'react'
import { askSavedSession, explainApiError } from '../services/api.js'

const prompts = [
  'Which part of my finances needs attention?',
  'Why should I focus on my emergency fund?',
  'How did the system arrive at this recommendation?',
]

export default function AdvisorChat({ userId, sessionId, stale = false }) {
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
      const contextTopic = [...messages].reverse().find((item) => item.response)?.response.topic
      const response = await askSavedSession(userId, sessionId, trimmed, contextTopic)
      setMessages((current) => [...current, { question: trimmed, response }])
      setQuestion('')
    } catch (requestError) { setError(explainApiError(requestError)) }
    finally { askingRef.current = false; setAsking(false) }
  }

  return <section className="advisor-chat" aria-labelledby="advisor-chat-heading">
    <p className="research-small-label">OPTIONAL ADVISOR CHAT</p>
    <h3 id="advisor-chat-heading">Ask about this saved run</h3>
    <p>These answers describe the saved run shown above. They use its recorded numbers, agent findings and decisions without calling an AI model. Messages are not saved to history.</p>
    {stale && <p className="advisor-chat-stale">Your profile has changed since this run. These answers still describe its earlier snapshot.</p>}
    <div className="advisor-chat-prompts" aria-label="Suggested questions">
      {prompts.map((prompt) => <button key={prompt} type="button" disabled={asking} onClick={() => ask(prompt)}>{prompt}</button>)}
    </div>
    {messages.length > 0 && <ol className="advisor-chat-messages" aria-label="Questions and answers" aria-live="polite">
      {messages.map((item, index) => <li key={index}>
        <p className="advisor-chat-question">You: {item.question}</p>
        <div className="advisor-chat-answer"><strong>Advisor answer from saved run</strong><p>{item.response.answer}</p>
          {item.response.evidence.length > 0 && <details><summary>Evidence from this run</summary><ul>
            {item.response.evidence.map((fact) => <li key={fact.id}><strong>{fact.label}</strong><span>{fact.detail}</span></li>)}
          </ul></details>}
        </div>
      </li>)}
    </ol>}
    <form className="advisor-chat-form" onSubmit={(event) => { event.preventDefault(); ask(question) }}>
      <label htmlFor="advisor-chat-question">Your question</label>
      <div><input id="advisor-chat-question" value={question} maxLength={500} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about this saved run" disabled={asking} />
        <button className="primary-action" type="submit" disabled={asking || question.trim().length < 3}>{asking ? 'Answering…' : 'Ask'}</button></div>
    </form>
    {error && <p role="alert" className="research-error">{error}</p>}
  </section>
}
