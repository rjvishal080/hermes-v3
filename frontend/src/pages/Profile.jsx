import { useState, useEffect } from 'react'
import { Save, Plus, X, User } from 'lucide-react'

const API = '/api'

export default function Profile() {
  const [profile, setProfile] = useState(null)
  const [saved,   setSaved]   = useState(false)
  const [newGoal, setNewGoal] = useState('')

  useEffect(() => {
    fetch(`${API}/profile`).then(r => r.json()).then(setProfile)
  }, [])

  async function save() {
    await fetch(`${API}/profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: profile.name, bio: profile.bio }),
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  if (!profile) return <div className="page dim" style={{ padding: 40 }}>Loading…</div>

  return (
    <div className="page" style={{ maxWidth: 520 }}>
      <div className="page-header">
        <h1>Profile</h1>
        <p>How Hermes knows you. Additional facts are learned from conversations.</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
            <div style={{ width: 42, height: 42, borderRadius: '50%', background: 'rgba(124,134,255,.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <User size={18} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <div style={{ fontWeight: 600 }}>{profile.name || 'Not set'}</div>
              <div style={{ fontSize: 11, color: 'var(--text3)' }}>Updated: {profile.last_updated?.slice(0, 10) || '—'}</div>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="form-field">
              <label>Name</label>
              <input value={profile.name || ''} onChange={e => setProfile(p => ({ ...p, name: e.target.value }))} placeholder="Revan" />
            </div>
            <div className="form-field">
              <label>Bio / context for Hermes</label>
              <textarea rows={3} value={profile.bio || ''} onChange={e => setProfile(p => ({ ...p, bio: e.target.value }))}
                placeholder="CS student, Arch Linux user, interested in cybersecurity and AI systems…" />
            </div>
          </div>
        </div>

        {/* Academic summary */}
        {profile.academic?.college && (
          <div className="card">
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10 }}>Academic</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12 }}>
              {[
                ['College',  profile.academic.college],
                ['CGPA',     profile.academic.cgpa],
                ['Semester', profile.academic.semester],
              ].filter(([, v]) => v).map(([l, v]) => (
                <div key={l} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ color: 'var(--text3)' }}>{l}</span>
                  <span>{v}</span>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 8 }}>Edit in Data → Academic</div>
          </div>
        )}

        <button className="btn primary" onClick={save} style={{ alignSelf: 'flex-start' }}>
          <Save size={13} /> {saved ? 'Saved!' : 'Save profile'}
        </button>
      </div>
    </div>
  )
}
