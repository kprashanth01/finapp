import { useState } from 'react'

const inputClass = 'mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-base focus:border-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-200'
const labelClass = 'block text-sm font-medium text-slate-700'

function UserForm({ user, onSave, saving, disabled }) {
  const [fields, setFields] = useState({
    name: user?.name ?? '',
    email: user?.email ?? '',
    age: user?.age ?? '',
    occupation: user?.occupation ?? '',
    monthly_income: user?.monthly_income ?? '',
  })

  function update(event) {
    setFields({ ...fields, [event.target.name]: event.target.value })
  }

  function submit(event) {
    event.preventDefault()
    onSave({
      name: fields.name.trim(),
      email: fields.email.trim(),
      age: fields.age === '' ? null : Number(fields.age),
      occupation: fields.occupation.trim() || null,
      monthly_income: fields.monthly_income,
    })
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">{user ? 'User details' : 'Create a user'}</h2>
        <p className="mt-1 text-sm text-slate-600">{user ? 'Update the details attached to this profile.' : 'This gives your financial profile a record to belong to.'}</p>
      </div>
      <fieldset disabled={saving || disabled} className="grid gap-5 sm:grid-cols-2">
        <label className={labelClass}>
          Name
          <input className={inputClass} name="name" value={fields.name} onChange={update} required maxLength="100" />
        </label>
        <label className={labelClass}>
          Email
          <input className={inputClass} name="email" type="email" value={fields.email} onChange={update} required />
        </label>
        <label className={labelClass}>
          Age (optional)
          <input className={inputClass} name="age" type="number" min="0" max="120" step="1" value={fields.age} onChange={update} />
        </label>
        <label className={labelClass}>
          Occupation (optional)
          <input className={inputClass} name="occupation" value={fields.occupation} onChange={update} maxLength="100" />
        </label>
        <label className={labelClass}>
          Current gross monthly income estimate (before tax)
          <input className={inputClass} name="monthly_income" type="number" min="0" step="0.01" value={fields.monthly_income} onChange={update} required />
          <span className="mt-1 block text-xs font-normal text-slate-500">Used for income-based ratios. Record income actually received in Months.</span>
        </label>
      </fieldset>
      <button type="submit" disabled={saving || disabled} className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50">
        {saving ? 'Saving…' : user ? 'Update user' : 'Create user'}
      </button>
    </form>
  )
}

export default UserForm
