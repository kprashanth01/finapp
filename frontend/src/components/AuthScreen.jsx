import { useState } from 'react'

const input = 'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base focus:border-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-200'

export default function AuthScreen({ mode = 'login', onMode, onSubmit, pending = false, error = '' }) {
  const [fields, setFields] = useState({ name: '', email: '', password: '', code: '' })
  const heading = mode === 'signup' ? 'Create your account' : mode === 'claim' ? 'Claim an earlier local profile' : 'Sign in'
  const label = mode === 'signup' ? 'Create account' : mode === 'claim' ? 'Claim profile' : 'Sign in'

  function change(event) { setFields({ ...fields, [event.target.name]: event.target.value }) }
  function submit(event) {
    event.preventDefault()
    onSubmit(mode, {
      ...(mode === 'signup' ? { name: fields.name.trim() } : {}),
      email: fields.email.trim(),
      password: fields.password,
      ...(mode === 'claim' ? { code: fields.code.trim() } : {}),
    })
  }

  return <div className="space-y-6">
    <div>
      <h2 className="text-2xl font-semibold">{heading}</h2>
      <p className="mt-2 text-sm text-slate-600">{mode === 'signup'
        ? 'Start with an account. Add your financial profile after signing in.'
        : mode === 'claim'
          ? 'Use the one-time claim code issued by your local administrator for your earlier profile.'
          : 'Return to your saved profile, goals, and advisory history.'}</p>
    </div>
    <form onSubmit={submit} className="space-y-4">
      <fieldset disabled={pending} className="space-y-4">
        {mode === 'signup' && <label className="block text-sm font-medium">Name<input className={input} name="name" autoComplete="name" required maxLength="100" value={fields.name} onChange={change} /></label>}
        <label className="block text-sm font-medium">Email<input className={input} name="email" type="email" autoComplete="email" required value={fields.email} onChange={change} /></label>
        {mode === 'claim' && <label className="block text-sm font-medium">One-time claim code<input className={input} name="code" autoComplete="off" required value={fields.code} onChange={change} /></label>}
        <label className="block text-sm font-medium">{mode === 'claim' ? 'New password' : 'Password'}
          <input className={input} name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required minLength={mode === 'login' ? undefined : 12} maxLength="128" value={fields.password} onChange={change} />
          {mode !== 'login' && <span className="mt-1 block text-xs font-normal text-slate-600">Use at least 12 characters.</span>}
        </label>
      </fieldset>
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      <button type="submit" disabled={pending} className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">{pending ? 'Please wait…' : label}</button>
    </form>
    <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-200 pt-5 text-sm">
      {mode !== 'login' && <button type="button" onClick={() => onMode('login')} className="underline">Sign in instead</button>}
      {mode !== 'signup' && <button type="button" onClick={() => onMode('signup')} className="underline">Create a new account</button>}
      {mode !== 'claim' && <button type="button" onClick={() => onMode('claim')} className="underline">Claim an earlier profile</button>}
    </div>
  </div>
}
