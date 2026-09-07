import { useState, useEffect } from 'react'
import { Brain, Target, BookOpen, Heart, DollarSign, Clock, GitBranch, Layers } from 'lucide-react'
import './Dashboard.css'

const API = '/api'

export default function Dashboard() {
  const [health, setHealth]   = useState(null)
  const [goals,  setGoals]    = useState([])
  const [profile,setProfile]  = useState(null)
  const [summary,setSummary]  = useState(null)

  useEffect(() => {
    fetch(`${API}/health`).then(r => r.json()).then(setHealth)
    fetch(`${API}/goals/active`).then(r => r.json()).then(d => setGoals(d.goals || []))
    fetch(`${API}/profile`).then(r => r.json()).then(setProfile)
    fetch(`${API}/memory/stats`).then(r => r.json()).then(setSummary)
  }, [])

  if (!health || !profile) return <div className="page"><div className="dim" style={{ padding: 40 }}>Loading…</div></div>

  const ms     = health.memory_stats || {}
  const colls  = ms.collections || {}
  const acad   = profile.academic || {}
  const fin    = profile.finances || {}
  const hlth   = profile.health || {}
  const st     = profile.screen_time || {}
  const graph  = ms.graph || {}

  const totalMem = (colls.memories || 0) + (colls.finances || 0) +
                   (colls.academic || 0) + (colls.documents || 0)

  return (
    <div className="page dashboard">
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Your life at a glance — powered by {ms.semantic || 0} semantic facts + {ms.episodic?.total || 0} episodes.</p>
      </div>

      {/* Memory system overview */}
      <div className="mem-grid">
        <MemCard icon={Brain}     color="accent"  label="Semantic facts"   value={ms.semantic || 0}           sub="structured" />
        <MemCard icon={Layers}    color="purple"  label="Episodic events"  value={ms.episodic?.total || 0}    sub="timeline" />
        <MemCard icon={BookOpen}  color="green"   label="Preferences"      value={ms.procedural?.total || 0}  sub="learned" />
        <MemCard icon={GitBranch} color="gold"    label="Graph nodes"      value={graph.entities || 0}        sub={`${graph.relations || 0} relations`} />
        <MemCard icon={Brain}     color="blue"    label="Vector memories"  value={totalMem}                   sub="retrievable" />
        <MemCard icon={Target}    color="red"     label="Active goals"     value={goals.length}               sub="tracked" />
      </div>

      <div className="dash-grid">

        {/* Active goals */}
        {goals.length > 0 && (
          <div className="card">
            <div className="card-hd"><Target size={14} style={{ color: 'var(--accent)' }} /> Active goals</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {goals.slice(0, 4).map(g => {
                const ms_done  = g.milestones.filter(m => m.done).length
                const ms_total = g.milestones.length
                const pct = ms_total > 0 ? (ms_done / ms_total) * 100 : null
                const days = g.deadline
                  ? Math.ceil((new Date(g.deadline) - new Date()) / 86400000)
                  : null
                return (
                  <div key={g.id} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                      <span style={{ fontWeight: 500 }}>{g.title}</span>
                      {days !== null && (
                        <span style={{ color: days <= 3 ? 'var(--red)' : days <= 7 ? 'var(--gold)' : 'var(--text3)', fontSize: 11 }}>
                          {days < 0 ? `${-days}d overdue` : `${days}d`}
                        </span>
                      )}
                    </div>
                    {pct !== null && (
                      <div style={{ height: 3, background: 'var(--bg3)', borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${pct}%`, background: 'var(--accent)', borderRadius: 2 }} />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Academic */}
        <div className="card">
          <div className="card-hd"><BookOpen size={14} style={{ color: 'var(--green)' }} /> Academic</div>
          {acad.college  && <InfoRow label="College"  value={acad.college} />}
          {acad.cgpa     && <InfoRow label="CGPA"     value={acad.cgpa} highlight />}
          {acad.semester && <InfoRow label="Semester" value={acad.semester} />}
          {acad.courses?.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div className="dim" style={{ fontSize: 11, marginBottom: 5 }}>COURSES</div>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {acad.courses.map(c => <span key={c} className="tag green" style={{ fontSize: 10 }}>{c}</span>)}
              </div>
            </div>
          )}
          {Object.entries(acad.attendance || {}).length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="dim" style={{ fontSize: 11, marginBottom: 5 }}>ATTENDANCE</div>
              {Object.entries(acad.attendance).map(([s, v]) => (
                <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, marginBottom: 4 }}>
                  <span style={{ width: 80, color: 'var(--text2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s}</span>
                  <div style={{ flex: 1, height: 5, background: 'var(--bg3)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${Math.min(+v, 100)}%`, background: +v < 75 ? 'var(--red)' : 'var(--green)', borderRadius: 2 }} />
                  </div>
                  <span style={{ color: +v < 75 ? 'var(--red)' : 'var(--text2)', width: 32, textAlign: 'right' }}>{v}%</span>
                </div>
              ))}
            </div>
          )}
          {!acad.college && <div className="dim" style={{ fontSize: 12 }}>Add academic data in the Data tab.</div>}
        </div>

        {/* Finance */}
        <div className="card">
          <div className="card-hd"><DollarSign size={14} style={{ color: 'var(--gold)' }} /> Finances</div>
          {fin.monthly_budget > 0 && <InfoRow label="Budget" value={`₹${fin.monthly_budget}/mo`} />}
          {Object.entries(fin.categories || {}).length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div className="dim" style={{ fontSize: 11, marginBottom: 6 }}>TOP CATEGORIES</div>
              {Object.entries(fin.categories).slice(0, 5).map(([cat, amt]) => {
                const max = Object.values(fin.categories)[0]
                return (
                  <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, marginBottom: 5 }}>
                    <span style={{ width: 90, color: 'var(--text2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cat}</span>
                    <div style={{ flex: 1, height: 5, background: 'var(--bg3)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${(amt / max) * 100}%`, background: 'var(--gold)', borderRadius: 2 }} />
                    </div>
                    <span style={{ color: 'var(--text2)', width: 60, textAlign: 'right' }}>₹{amt.toLocaleString('en-IN')}</span>
                  </div>
                )
              })}
            </div>
          )}
          {!fin.cashiro_linked && <div className="dim" style={{ fontSize: 12 }}>Upload Cashiro CSV in Data tab.</div>}
        </div>

        {/* Health + screen time */}
        <div className="card">
          <div className="card-hd"><Heart size={14} style={{ color: 'var(--red)' }} /> Health & Screen Time</div>
          {hlth.sleep_avg_hrs  > 0 && <InfoRow label="Sleep"    value={`${hlth.sleep_avg_hrs}h/night`} />}
          {hlth.exercise_days_week > 0 && <InfoRow label="Exercise" value={`${hlth.exercise_days_week} days/week`} />}
          {hlth.weight_kg          && <InfoRow label="Weight"   value={`${hlth.weight_kg}kg`} />}
          {st.daily_avg_mins   > 0 && (
            <InfoRow label="Screen time" value={`${st.daily_avg_mins}min/day`}
              highlight={st.daily_avg_mins > 360} />
          )}
          {st.top_apps && Object.keys(st.top_apps).length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div className="dim" style={{ fontSize: 11, marginBottom: 5 }}>TOP APPS</div>
              {Object.entries(st.top_apps).slice(0, 4).map(([app, mins]) => (
                <div key={app} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '2px 0', color: 'var(--text2)' }}>
                  <span>{app}</span><span>{mins}m</span>
                </div>
              ))}
            </div>
          )}
          {!hlth.sleep_avg_hrs && <div className="dim" style={{ fontSize: 12 }}>Log health data in Data tab.</div>}
        </div>

        {/* Memory type breakdown */}
        {summary && (
          <div className="card">
            <div className="card-hd"><Brain size={14} style={{ color: 'var(--purple)' }} /> Memory breakdown</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                ['Semantic facts',    ms.semantic || 0,          'accent'],
                ['Episodic events',   ms.episodic?.total || 0,   'purple'],
                ['Preferences',       ms.procedural?.total || 0, 'green'],
                ['Conversations',     colls.memories || 0,       'blue'],
                ['Finance records',   colls.finances || 0,       'gold'],
                ['Academic records',  colls.academic || 0,       'green'],
                ['Documents/PDFs',    colls.documents || 0,      'gray'],
              ].map(([label, count, color]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12 }}>
                  <span style={{ color: 'var(--text2)' }}>{label}</span>
                  <span className={`tag ${color}`} style={{ fontSize: 10 }}>{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

function MemCard({ icon: Icon, color, label, value, sub }) {
  const colors = { accent: 'var(--accent)', purple: 'var(--purple)', green: 'var(--green)', gold: 'var(--gold)', blue: 'var(--accent)', red: 'var(--red)' }
  const bg     = { accent: 'rgba(124,134,255,.1)', purple: 'rgba(176,126,255,.1)', green: 'rgba(78,204,163,.1)', gold: 'rgba(240,168,50,.1)', blue: 'rgba(124,134,255,.1)', red: 'rgba(255,107,107,.1)' }
  return (
    <div className="mem-card">
      <div style={{ width: 32, height: 32, borderRadius: 8, background: bg[color], display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <Icon size={15} style={{ color: colors[color] }} />
      </div>
      <div>
        <div style={{ fontSize: 20, fontWeight: 600, lineHeight: 1.2 }}>{value}</div>
        <div style={{ fontSize: 11, color: 'var(--text2)' }}>{label} <span className="dim">{sub}</span></div>
      </div>
    </div>
  )
}

function InfoRow({ label, value, highlight }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ color: 'var(--text3)' }}>{label}</span>
      <span style={{ color: highlight ? 'var(--red)' : 'var(--text)', fontWeight: highlight ? 600 : 400 }}>{value}</span>
    </div>
  )
}
