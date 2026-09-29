import { useCallback, useEffect, useRef, useState } from 'react'
import { createGoal, updateGoal, setGoalArchived, getGoals, explainApiError } from '../services/api.js'

export default function useGoals(userId) {
  const [goals, setGoals] = useState([])
  const [loading, setLoading] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const generation = useRef(0)
  const busy = useRef(false)
  const owner = useRef(userId)
  owner.current = userId

  const reload = useCallback(async () => {
    if (!userId || busy.current) return
    const token = ++generation.current
    setLoading(true)
    setError('')
    try {
      const rows = await getGoals(userId, { includeArchived: true })
      if (token === generation.current && owner.current === userId) setGoals(rows)
    } catch (e) {
      if (token === generation.current && owner.current === userId) setError(explainApiError(e))
    } finally {
      if (token === generation.current && owner.current === userId) setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    setGoals([])
    reload()
    return () => { generation.current += 1 }
  }, [reload])

  async function mutate(operation) {
    if (busy.current || !userId) return null
    busy.current = true
    const token = ++generation.current
    setPending(true)
    setError('')
    try {
      const saved = await operation()
      if (token !== generation.current || owner.current !== userId) return null
      // Use the successful write response; a failed subsequent read must not look like a failed save.
      setGoals((rows) => [...rows.filter((g) => g.id !== saved.id), saved].sort((a, b) => a.id - b.id))
      return saved
    } finally {
      busy.current = false
      if (owner.current === userId) { setPending(false); setLoading(false) }
    }
  }

  return { goals, loading, pending, error, reload,
    create: (values) => mutate(() => createGoal(userId, values)),
    update: (id, values) => mutate(() => updateGoal(userId, id, values)),
    setArchived: (id, archived) => mutate(() => setGoalArchived(userId, id, archived)),
  }
}
