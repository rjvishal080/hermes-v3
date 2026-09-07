import { useState, useEffect } from 'react'
import { Target, Plus, CheckCircle, Clock, AlertTriangle, ChevronDown, ChevronRight, Trash2, Edit3 } from 'lucide-react'
import './Goals.css'

const API = '/api'

const CATEGORIES = ['career', 'academic', 'health', 'financial', 'personal', 'skill']
const CAT_COLORS = { career: 'blue', academic: 'green', health: 'red', financial: 'gold', personal: 'purple', skill: 'gray' }
const PRIORITY_LABELS = { 1: 'Low', 2: 'Medium', 3: 'Normal', 4: 'High', 5: 'Critical' }
const PRIORITY_COLORS = { 1: 'gray', 2: 'gray', 3: 'blue', 4: 'gold', 5: 'red' }

export default function Goals() {
  const [goals, setGoals]       = useState([])
  const [alerts, setAlerts]     = useState([])
  const [showForm, setShowForm] = useState(false)
  const [expanded, setExpanded] = useState({})

  const [form, setForm] = useState({
    title: '', description: '', category: 'personal',
    priority: 3, deadline: '', milestones: '',
  })

  useEffect(() => { fetchGoals(); fetchAlerts() }, [])

  async function fetchGoals() {
    const r = await fetch(`${API}/goals`)
    const d = await r.json()
    setGoals(d.goals || [])
  }

  async function fetchAlerts() {
    const r = await fetch(`${API}/goals/alerts`)
    const d = await r.json()
    setAlerts(d.alerts || [])
  }

  async function createGoal(e) {
    e.preventDefault()
    const milestones = form.milestones.split('\n').map(s => s.trim()).filter(Boolean)
    await fetch(`${API}/goals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, milestones }),
    })
    setForm({ title: '', description: '', category: 'personal', priority: 3, deadline: '', milestones: '' })
    setShowForm(false)
    fetchGoals()
  }

  async function updateStatus(gid, status) {
    await fetch(`${API}/goals/${gid}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    fetchGoals()
  }

  async function completeMilestone(gid, text) {
    await fetch(`${API}/goals/${gid}/milestone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ milestone_text: text }),
    })
    fetchGoals()
  }

  async function deleteGoal(gid) {
    await fetch(`${API}/goals/${gid}`, { method: 'DELETE' })
    fetchGoals()
  }

  function toggleExpand(gid) {
    setExpanded(p => ({ ...p, [gid]: !p[gid] }))
  }

  const active    = goals.filter(g => g.status === 'active')
  const completed = goals.filter(g => g.status === 'completed')
  const paused    = goals.filter(g => g.status === 'paused')

  return (
    <div className="page goals-page">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1>Goals</h1>
            <p>{active.length} active · {completed.length} completed</p>
          </div>
          <button className="btn primary" onClick={() => setShowForm(p => !p)}>
            <Plus size={13} /> New goal
          </button>
        </div>
      </div>

      {/* Deadline alerts */}
      {alerts.length > 0 && (
        <div className="alerts-bar">
          {alerts.map(a => (
            <div key={a.id} className={`alert-chip ${a.days_left <= 0 ? 'overdue' : a.days_left <= 3 ? 'urgent' : 'soon'}`}>
              <AlertTriangle size={11} />
              <span>{a.title}</span>
              <span className="alert-days">
                {a.days_left <= 0 ? `${-a.days_left}d overdue` : `${a.days_left}d left`}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* New goal form */}
      {showForm && (
        <div className="card" style={{ marginBottom: 20, animation: 'fadeIn .2s' }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 14 }}>New Goal</div>
          <form onSubmit={createGoal} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="form-grid">
              <div className="form-field" style={{ gridColumn: '1/-1' }}>
                <label>Title</label>
                <input value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))}
                  placeholder="Get ML internship at Zoho" required />
              </div>
              <div className="form-field">
                <label>Category</label>
                <select value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))}>
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-field">
                <label>Priority</label>
                <select value={form.priority} onChange={e => setForm(p => ({ ...p, priority: +e.target.value }))}>
                  {Object.entries(PRIORITY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              <div className="form-field">
                <label>Deadline (optional)</label>
                <input type="date" value={form.deadline} onChange={e => setForm(p => ({ ...p, deadline: e.target.value }))} />
              </div>
              <div className="form-field">
                <label>Description</label>
                <input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                  placeholder="Land a 6-month ML role at a product company" />
              </div>
              <div className="form-field" style={{ gridColumn: '1/-1' }}>
                <label>Milestones (one per line)</label>
                <textarea rows={3} value={form.milestones} onChange={e => setForm(p => ({ ...p, milestones: e.target.value }))}
                  placeholder={"Build ML project on GitHub\nComplete DSA prep (Striver A2Z)\nApply to 10 companies"} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn primary" type="submit">Create goal</button>
              <button className="btn" type="button" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Active goals */}
      {active.length > 0 && (
        <section className="goal-section">
          <div className="section-label">ACTIVE</div>
          <div className="goal-list">
            {active.map(g => (
              <GoalCard key={g.id} goal={g}
                expanded={expanded[g.id]}
                onToggle={() => toggleExpand(g.id)}
                onStatusChange={updateStatus}
                onMilestone={completeMilestone}
                onDelete={deleteGoal}
              />
            ))}
          </div>
        </section>
      )}

      {paused.length > 0 && (
        <section className="goal-section">
          <div className="section-label">PAUSED</div>
          <div className="goal-list">
            {paused.map(g => (
              <GoalCard key={g.id} goal={g} expanded={expanded[g.id]}
                onToggle={() => toggleExpand(g.id)} onStatusChange={updateStatus}
                onMilestone={completeMilestone} onDelete={deleteGoal} />
            ))}
          </div>
        </section>
      )}

      {completed.length > 0 && (
        <section className="goal-section">
          <div className="section-label">COMPLETED</div>
          <div className="goal-list">
            {completed.map(g => (
              <GoalCard key={g.id} goal={g} expanded={expanded[g.id]}
                onToggle={() => toggleExpand(g.id)} onStatusChange={updateStatus}
                onMilestone={completeMilestone} onDelete={deleteGoal} />
            ))}
          </div>
        </section>
      )}

      {goals.length === 0 && !showForm && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text3)' }}>
          <Target size={32} style={{ marginBottom: 12, opacity: .3 }} />
          <p>No goals yet. Create one to let Hermes reason about your direction.</p>
        </div>
      )}
    </div>
  )
}

function GoalCard({ goal, expanded, onToggle, onStatusChange, onMilestone, onDelete }) {
  const catColor  = CAT_COLORS[goal.category] || 'gray'
  const priColor  = PRIORITY_COLORS[goal.priority] || 'gray'
  const priLabel  = PRIORITY_LABELS[goal.priority] || ''
  const msTotal   = goal.milestones.length
  const msDone    = goal.milestones.filter(m => m.done).length
  const pct       = msTotal > 0 ? Math.round((msDone / msTotal) * 100) : null
  const isComplete = goal.status === 'completed'

  let deadlineEl = null
  if (goal.deadline) {
    const days = Math.ceil((new Date(goal.deadline) - new Date()) / 86400000)
    const cls  = days < 0 ? 'red' : days <= 3 ? 'red' : days <= 7 ? 'gold' : 'gray'
    deadlineEl = (
      <span className={`tag ${cls}`} style={{ fontSize: 10 }}>
        <Clock size={9} />
        {days < 0 ? `${-days}d overdue` : `${days}d left`}
      </span>
    )
  }

  return (
    <div className={`goal-card ${isComplete ? 'completed' : ''}`}>
      <div className="goal-header" onClick={onToggle}>
        <div className="goal-header-left">
          <span className={`tag ${catColor}`} style={{ fontSize: 10 }}>{goal.category}</span>
          <span className={`tag ${priColor}`} style={{ fontSize: 10 }}>{priLabel}</span>
          {deadlineEl}
        </div>
        <div className="goal-actions">
          {!isComplete && (
            <button className="btn ghost" style={{ padding: '3px 8px', fontSize: 11 }}
              onClick={e => { e.stopPropagation(); onStatusChange(goal.id, 'completed') }}>
              <CheckCircle size={11} /> Done
            </button>
          )}
          <button className="btn ghost danger" style={{ padding: '3px 6px' }}
            onClick={e => { e.stopPropagation(); onDelete(goal.id) }}>
            <Trash2 size={11} />
          </button>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>

      <div className="goal-title">{goal.title}</div>
      {goal.description && <div className="goal-desc">{goal.description}</div>}

      {pct !== null && (
        <div className="progress-wrap">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <span className="dim" style={{ fontSize: 11 }}>{msDone}/{msTotal}</span>
        </div>
      )}

      {expanded && (
        <div className="goal-body">
          {goal.milestones.length > 0 && (
            <div className="milestones">
              <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 6, fontWeight: 600 }}>MILESTONES</div>
              {goal.milestones.map((m, i) => (
                <div key={i} className={`milestone ${m.done ? 'done' : ''}`}
                  onClick={() => !m.done && onMilestone(goal.id, m.text)}>
                  <div className="ms-dot" />
                  <span>{m.text}</span>
                  {m.done && <CheckCircle size={11} style={{ color: 'var(--green)', marginLeft: 'auto' }} />}
                </div>
              ))}
            </div>
          )}
          {goal.progress_notes.length > 0 && (
            <div className="progress-notes">
              <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 6, fontWeight: 600 }}>PROGRESS LOG</div>
              {goal.progress_notes.slice(-3).map((n, i) => (
                <div key={i} className="progress-note">
                  <span className="dim" style={{ fontSize: 10 }}>{n.date}</span>
                  <span>{n.text}</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            {goal.status !== 'paused' && !isComplete && (
              <button className="btn ghost" style={{ fontSize: 11 }}
                onClick={() => onStatusChange(goal.id, 'paused')}>Pause</button>
            )}
            {goal.status === 'paused' && (
              <button className="btn" style={{ fontSize: 11 }}
                onClick={() => onStatusChange(goal.id, 'active')}>Resume</button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
