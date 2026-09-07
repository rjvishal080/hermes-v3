import { useState } from 'react'
import { Upload, Clock, GraduationCap, Heart, BookOpen, FileText, CheckCircle } from 'lucide-react'
import './Ingest.css'

const API = '/api'

const TABS = [
  { id: 'cashiro',    icon: Upload,        label: 'Cashiro' },
  { id: 'academic',  icon: GraduationCap, label: 'Academic' },
  { id: 'screentime',icon: Clock,         label: 'Screen Time' },
  { id: 'health',    icon: Heart,         label: 'Health' },
  { id: 'log',       icon: BookOpen,      label: 'Life Log' },
  { id: 'pdf',       icon: FileText,      label: 'PDF / Notes' },
]

function Toast({ msg, onClose }) {
  if (!msg) return null
  return (
    <div className="toast" onClick={onClose}>
      <CheckCircle size={13} /> {msg}
    </div>
  )
}

export default function Ingest() {
  const [tab,     setTab]     = useState('cashiro')
  const [toast,   setToast]   = useState('')
  const [loading, setLoading] = useState(false)

  function ok(msg) { setToast(msg); setTimeout(() => setToast(''), 3500) }

  // ── Cashiro ────────────────────────────────────────────────────────────────
  async function uploadCashiro(e) {
    const file = e.target.files[0]; if (!file) return
    setLoading(true)
    const form = new FormData(); form.append('file', file)
    const r = await fetch(`${API}/ingest/cashiro`, { method: 'POST', body: form })
    const d = await r.json()
    setLoading(false)
    ok(`Imported ${d.imported} transactions across ${d.months} months`)
    e.target.value = ''
  }

  // ── Academic ───────────────────────────────────────────────────────────────
  const [ac, setAc] = useState({ college: '', semester: '', cgpa: '', portal_url: '',
    courses_raw: '', attendance_raw: '', grades_raw: '' })

  async function submitAcademic(e) {
    e.preventDefault()
    const courses    = ac.courses_raw.split(',').map(s => s.trim()).filter(Boolean)
    const attendance = {}
    ac.attendance_raw.split('\n').forEach(line => {
      const [s, v] = line.split(':').map(s => s.trim()); if (s && v) attendance[s] = +v
    })
    const grades = {}
    ac.grades_raw.split('\n').forEach(line => {
      const [s, g] = line.split(':').map(s => s.trim()); if (s && g) grades[s] = g
    })
    await fetch(`${API}/ingest/academic`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...ac, courses, attendance, grades }),
    })
    ok('Academic data stored')
  }

  // ── Screen time ────────────────────────────────────────────────────────────
  const [st, setSt] = useState({ daily_avg_mins: '', top_apps_raw: '', date: '' })

  async function submitScreenTime(e) {
    e.preventDefault()
    const apps = {}
    st.top_apps_raw.split('\n').forEach(line => {
      const [app, mins] = line.split(':').map(s => s.trim())
      if (app && mins && !isNaN(+mins)) apps[app] = +mins
    })
    await fetch(`${API}/ingest/screentime`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ daily_avg_mins: +st.daily_avg_mins, top_apps: apps, date: st.date }),
    })
    ok('Screen time logged')
  }

  // ── Health ─────────────────────────────────────────────────────────────────
  const [hl, setHl] = useState({ sleep_avg_hrs: '', exercise_days_week: '', weight_kg: '', notes: '', date: '' })

  async function submitHealth(e) {
    e.preventDefault()
    await fetch(`${API}/ingest/health`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sleep_avg_hrs: +hl.sleep_avg_hrs || null,
        exercise_days_week: +hl.exercise_days_week || null,
        weight_kg: +hl.weight_kg || null,
        notes: hl.notes, date: hl.date,
      }),
    })
    ok('Health data stored')
  }

  // ── Log ────────────────────────────────────────────────────────────────────
  const [log, setLog] = useState({ content: '', category: 'general', date: '', emotion: 'neutral', importance: 3 })

  async function submitLog(e) {
    e.preventDefault()
    await fetch(`${API}/ingest/log`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(log),
    })
    ok('Entry logged to episodic memory')
    setLog({ content: '', category: 'general', date: '', emotion: 'neutral', importance: 3 })
  }

  // ── PDF ────────────────────────────────────────────────────────────────────
  const [pdfTitle, setPdfTitle]   = useState('')
  const [pdfSubject, setPdfSubject] = useState('general')

  async function uploadPdf(e) {
    const file = e.target.files[0]; if (!file) return
    setLoading(true)
    const form = new FormData()
    form.append('file', file)
    const params = new URLSearchParams({ title: pdfTitle || file.name, subject: pdfSubject })
    const r = await fetch(`${API}/ingest/pdf?${params}`, { method: 'POST', body: form })
    const d = await r.json()
    setLoading(false)
    if (d.error) { ok(`Error: ${d.error}`); return }
    ok(`PDF ingested: ${d.pages} pages, ${d.chunks_stored} chunks stored`)
    e.target.value = ''
  }

  return (
    <div className="page ingest-page">
      <div className="page-header">
        <h1>Data Ingestion</h1>
        <p>Feed Hermes — every input flows into the right memory type.</p>
      </div>

      <Toast msg={toast} onClose={() => setToast('')} />

      <div className="ingest-tabs">
        {TABS.map(t => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            <t.icon size={13} /> {t.label}
          </button>
        ))}
      </div>

      <div className="ingest-body">

        {/* Cashiro */}
        {tab === 'cashiro' && (
          <div className="section">
            <h2>Cashiro / Bank Statement</h2>
            <p className="section-desc">Upload CSV export. Parsed into finance collection + semantic facts + episodic events.</p>
            <label className="upload-zone">
              <Upload size={22} />
              <span>{loading ? 'Processing…' : 'Click to upload CSV'}</span>
              <input type="file" accept=".csv" onChange={uploadCashiro} hidden disabled={loading} />
            </label>
            <div className="hint">
              <strong>Cashiro:</strong> Settings → Export → CSV &nbsp;|&nbsp;
              <strong>PhonePe:</strong> Transactions → Download Statement &nbsp;|&nbsp;
              <strong>Any bank:</strong> Net banking → Account statement → CSV
            </div>
          </div>
        )}

        {/* Academic */}
        {tab === 'academic' && (
          <form className="section" onSubmit={submitAcademic}>
            <h2>Academic Data</h2>
            <p className="section-desc">Stored as semantic facts + graph relationships + episodic alerts for low attendance.</p>
            <div className="form-grid">
              <div className="form-field">
                <label>College</label>
                <input value={ac.college} onChange={e => setAc(p => ({ ...p, college: e.target.value }))} placeholder="SJIT" />
              </div>
              <div className="form-field">
                <label>Semester</label>
                <input value={ac.semester} onChange={e => setAc(p => ({ ...p, semester: e.target.value }))} placeholder="7th" />
              </div>
              <div className="form-field">
                <label>CGPA</label>
                <input value={ac.cgpa} onChange={e => setAc(p => ({ ...p, cgpa: e.target.value }))} placeholder="8.2" />
              </div>
              <div className="form-field">
                <label>Portal URL</label>
                <input value={ac.portal_url} onChange={e => setAc(p => ({ ...p, portal_url: e.target.value }))} placeholder="https://erp.sjit.ac.in" />
              </div>
            </div>
            <div className="form-field">
              <label>Courses (comma separated)</label>
              <input value={ac.courses_raw} onChange={e => setAc(p => ({ ...p, courses_raw: e.target.value }))} placeholder="OS, DBMS, CN, AI, SE" />
            </div>
            <div className="form-grid">
              <div className="form-field">
                <label>Attendance (Subject: %, one per line)</label>
                <textarea rows={5} value={ac.attendance_raw} onChange={e => setAc(p => ({ ...p, attendance_raw: e.target.value }))}
                  placeholder={"OS: 82\nDBMS: 68\nCN: 91"} />
              </div>
              <div className="form-field">
                <label>Grades (Subject: grade, one per line)</label>
                <textarea rows={5} value={ac.grades_raw} onChange={e => setAc(p => ({ ...p, grades_raw: e.target.value }))}
                  placeholder={"OS: A\nDBMS: B+\nCN: A+"} />
              </div>
            </div>
            <button className="btn primary" type="submit">Save academic data</button>
          </form>
        )}

        {/* Screen time */}
        {tab === 'screentime' && (
          <form className="section" onSubmit={submitScreenTime}>
            <h2>Screen Time</h2>
            <p className="section-desc">Android: Digital Wellbeing → Dashboard. iOS: Screen Time → See All Activity.</p>
            <div className="form-grid">
              <div className="form-field">
                <label>Daily average (minutes)</label>
                <input type="number" value={st.daily_avg_mins} onChange={e => setSt(p => ({ ...p, daily_avg_mins: e.target.value }))} placeholder="240" required />
              </div>
              <div className="form-field">
                <label>Date</label>
                <input type="date" value={st.date} onChange={e => setSt(p => ({ ...p, date: e.target.value }))} />
              </div>
            </div>
            <div className="form-field">
              <label>Top apps (App: minutes, one per line)</label>
              <textarea rows={5} value={st.top_apps_raw} onChange={e => setSt(p => ({ ...p, top_apps_raw: e.target.value }))}
                placeholder={"Instagram: 60\nYouTube: 45\nWhatsApp: 30"} />
            </div>
            <button className="btn primary" type="submit">Log screen time</button>
          </form>
        )}

        {/* Health */}
        {tab === 'health' && (
          <form className="section" onSubmit={submitHealth}>
            <h2>Health</h2>
            <div className="form-grid">
              <div className="form-field">
                <label>Sleep avg (hrs/night)</label>
                <input type="number" step="0.5" value={hl.sleep_avg_hrs} onChange={e => setHl(p => ({ ...p, sleep_avg_hrs: e.target.value }))} placeholder="7.5" />
              </div>
              <div className="form-field">
                <label>Exercise (days/week)</label>
                <input type="number" value={hl.exercise_days_week} onChange={e => setHl(p => ({ ...p, exercise_days_week: e.target.value }))} placeholder="4" />
              </div>
              <div className="form-field">
                <label>Weight (kg)</label>
                <input type="number" step="0.1" value={hl.weight_kg} onChange={e => setHl(p => ({ ...p, weight_kg: e.target.value }))} placeholder="68" />
              </div>
              <div className="form-field">
                <label>Date</label>
                <input type="date" value={hl.date} onChange={e => setHl(p => ({ ...p, date: e.target.value }))} />
              </div>
            </div>
            <div className="form-field">
              <label>Notes</label>
              <textarea rows={3} value={hl.notes} onChange={e => setHl(p => ({ ...p, notes: e.target.value }))} placeholder="Feeling low energy lately…" />
            </div>
            <button className="btn primary" type="submit">Save health data</button>
          </form>
        )}

        {/* Life log */}
        {tab === 'log' && (
          <form className="section" onSubmit={submitLog}>
            <h2>Life Log</h2>
            <p className="section-desc">Goes directly into episodic memory with emotion and importance tagging.</p>
            <div className="form-grid">
              <div className="form-field">
                <label>Category</label>
                <select value={log.category} onChange={e => setLog(p => ({ ...p, category: e.target.value }))}>
                  {['general','mood','event','goal','thought','health','achievement','issue','academic','finance'].map(c =>
                    <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-field">
                <label>Emotion</label>
                <select value={log.emotion} onChange={e => setLog(p => ({ ...p, emotion: e.target.value }))}>
                  {['neutral','positive','negative'].map(e => <option key={e} value={e}>{e}</option>)}
                </select>
              </div>
              <div className="form-field">
                <label>Importance (1–5)</label>
                <input type="number" min={1} max={5} value={log.importance} onChange={e => setLog(p => ({ ...p, importance: +e.target.value }))} />
              </div>
              <div className="form-field">
                <label>Date</label>
                <input type="date" value={log.date} onChange={e => setLog(p => ({ ...p, date: e.target.value }))} />
              </div>
            </div>
            <div className="form-field">
              <label>Entry</label>
              <textarea rows={4} value={log.content} onChange={e => setLog(p => ({ ...p, content: e.target.value }))}
                placeholder="Finished the OS assignment, went for a run, feeling good about placement prep…" required />
            </div>
            <button className="btn primary" type="submit">Log entry</button>
          </form>
        )}

        {/* PDF */}
        {tab === 'pdf' && (
          <div className="section">
            <h2>PDF / Lecture Notes</h2>
            <p className="section-desc">Pages are chunked and stored in the documents collection. Hermes can then answer questions from your notes.</p>
            <div className="form-grid">
              <div className="form-field">
                <label>Title (optional)</label>
                <input value={pdfTitle} onChange={e => setPdfTitle(e.target.value)} placeholder="OS Unit 3 Notes" />
              </div>
              <div className="form-field">
                <label>Subject</label>
                <input value={pdfSubject} onChange={e => setPdfSubject(e.target.value)} placeholder="Operating Systems" />
              </div>
            </div>
            <label className="upload-zone" style={{ marginTop: 12 }}>
              <FileText size={22} />
              <span>{loading ? 'Processing PDF…' : 'Click to upload PDF'}</span>
              <input type="file" accept=".pdf" onChange={uploadPdf} hidden disabled={loading} />
            </label>
            <div className="hint">
              Pages are split into 800-char chunks with 200-char overlap.
              Ask Hermes questions like "What does my OS notes say about scheduling?" and it will retrieve the relevant chunks.
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
