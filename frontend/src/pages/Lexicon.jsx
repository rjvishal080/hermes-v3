import { useState, useEffect } from 'react'
import { Plus, Trash2, Eye, BookOpen, Settings, Link, Zap } from 'lucide-react'
import './Lexicon.css'

const API = '/api/lexicon'

const TERM_CATS    = ['slang', 'personal', 'technical', 'cultural', 'emotional', 'irony']
const STYLE_CATS   = ['tone', 'format', 'address', 'energy', 'forbidden', 'preferred']
const CAT_COLORS   = { slang: 'blue', personal: 'purple', technical: 'green', cultural: 'gold', emotional: 'red', irony: 'gray' }
const STYLE_COLORS = { tone: 'blue', format: 'gray', address: 'green', energy: 'gold', forbidden: 'red', preferred: 'green' }

const TABS = [
  { id: 'terms',      icon: BookOpen,  label: 'Vocabulary' },
  { id: 'style',      icon: Settings,  label: 'Style rules' },
  { id: 'references', icon: Link,      label: 'References' },
  { id: 'preview',    icon: Eye,       label: 'Preview' },
]

// Starter examples to show the user what's possible
const EXAMPLE_TERMS = [
  { term: 'tonyad', meaning: 'got beaten or outcompeted by someone who wanted to win against you specifically', category: 'personal', examples: ['I got tonyad in the hackathon bro', 'he completely tonyad me in the DSA round'], context: 'used when a competitor specifically targets you and wins' },
  { term: 'larp', meaning: "pretend to know something you don't actually know or understand", category: 'slang', examples: ["I don't want to larp — I genuinely want to learn this", "stop larping like you know systems programming"], context: "negative connotation — pretending without real knowledge" },
]

const EXAMPLE_RULES = [
  { rule: "Match my energy — casual message gets casual reply, hype message gets hype reply", category: 'energy' },
  { rule: "Never say 'certainly', 'absolutely', 'of course' — sounds like a corporate bot", category: 'forbidden' },
  { rule: "Be direct and honest, don't sugarcoat", category: 'tone' },
  { rule: "I say 'bro' as a neutral term — you can use it back naturally", category: 'address' },
]

function Toast({ msg }) {
  if (!msg) return null
  return <div className="lex-toast"><Zap size={12} /> {msg}</div>
}

export default function Lexicon() {
  const [tab,        setTab]      = useState('terms')
  const [terms,      setTerms]    = useState([])
  const [rules,      setRules]    = useState([])
  const [refs,       setRefs]     = useState([])
  const [preview,    setPreview]  = useState('')
  const [stats,      setStats]    = useState(null)
  const [toast,      setToast]    = useState('')

  // Term form
  const [tf, setTf] = useState({ term: '', meaning: '', category: 'slang', examples: '', context: '' })
  // Style form
  const [sf, setSf] = useState({ rule: '', category: 'tone', strength: 1.0 })
  // Ref form
  const [rf, setRf] = useState({ trigger: '', meaning: '', is_ironic: false })

  useEffect(() => {
    fetchAll()
    fetchStats()
  }, [])

  async function fetchAll() {
    const [t, r, ref] = await Promise.all([
      fetch(`${API}/terms`).then(r => r.json()),
      fetch(`${API}/style`).then(r => r.json()),
      fetch(`${API}/references`).then(r => r.json()),
    ])
    setTerms(t.terms || [])
    setRules(r.rules || [])
    setRefs(ref.references || [])
  }

  async function fetchStats() {
    const r = await fetch(`${API}/stats`)
    setStats(await r.json())
  }

  async function fetchPreview() {
    const r = await fetch(`${API}/prompt-block`)
    const d = await r.json()
    setPreview(d.block || 'Nothing in lexicon yet.')
  }

  function ok(msg) { setToast(msg); setTimeout(() => setToast(''), 2500) }

  // ── Terms ──────────────────────────────────────────────────────────────────
  async function addTerm(e) {
    e.preventDefault()
    const examples = tf.examples.split('\n').map(s => s.trim()).filter(Boolean)
    await fetch(`${API}/terms`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...tf, examples }),
    })
    ok(`"${tf.term}" saved`)
    setTf({ term: '', meaning: '', category: 'slang', examples: '', context: '' })
    fetchAll(); fetchStats()
  }

  async function deleteTerm(id) {
    await fetch(`${API}/terms/${id}`, { method: 'DELETE' })
    fetchAll(); fetchStats()
  }

  // ── Style ──────────────────────────────────────────────────────────────────
  async function addStyle(e) {
    e.preventDefault()
    await fetch(`${API}/style`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sf),
    })
    ok('Style rule saved')
    setSf({ rule: '', category: 'tone', strength: 1.0 })
    fetchAll(); fetchStats()
  }

  async function deleteStyle(id) {
    await fetch(`${API}/style/${id}`, { method: 'DELETE' })
    fetchAll()
  }

  // ── References ─────────────────────────────────────────────────────────────
  async function addRef(e) {
    e.preventDefault()
    await fetch(`${API}/references`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rf),
    })
    ok(`"${rf.trigger}" saved`)
    setRf({ trigger: '', meaning: '', is_ironic: false })
    fetchAll(); fetchStats()
  }

  async function deleteRef(id) {
    await fetch(`${API}/references/${id}`, { method: 'DELETE' })
    fetchAll()
  }

  // ── Load example ───────────────────────────────────────────────────────────
  async function loadExamples() {
    for (const t of EXAMPLE_TERMS) {
      await fetch(`${API}/terms`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(t),
      })
    }
    for (const r of EXAMPLE_RULES) {
      await fetch(`${API}/style`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(r),
      })
    }
    ok('Example vocabulary loaded!')
    fetchAll(); fetchStats()
  }

  return (
    <div className="page lex-page">
      <Toast msg={toast} />

      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>Personal Lexicon</h1>
            <p>Teach Hermes your vocabulary, slang, and communication style.</p>
          </div>
          {stats && (
            <div className="lex-stats">
              <span className="tag blue">{stats.terms} terms</span>
              <span className="tag purple">{stats.style_rules} style rules</span>
              <span className="tag gold">{stats.references} references</span>
            </div>
          )}
        </div>
      </div>

      {/* Starter prompt */}
      {stats && stats.terms === 0 && stats.style_rules === 0 && (
        <div className="starter-card">
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Getting started</div>
          <p style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 12, lineHeight: 1.6 }}>
            Teach Hermes how you actually talk. Add your slang, expressions, and communication preferences — then every response will feel natural and personal, not generic.
          </p>
          <button className="btn primary" onClick={loadExamples}>
            <Zap size={13} /> Load starter examples (tonyad, larp, style rules)
          </button>
        </div>
      )}

      <div className="lex-tabs">
        {TABS.map(t => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? 'active' : ''}`}
            onClick={() => { setTab(t.id); if (t.id === 'preview') fetchPreview() }}>
            <t.icon size={13} /> {t.label}
          </button>
        ))}
      </div>

      {/* ── Vocabulary ── */}
      {tab === 'terms' && (
        <div className="lex-section">
          <form className="lex-form" onSubmit={addTerm}>
            <div className="form-row-3">
              <div className="form-field">
                <label>Term / phrase</label>
                <input value={tf.term} onChange={e => setTf(p => ({ ...p, term: e.target.value }))}
                  placeholder='e.g. tonyad' required />
              </div>
              <div className="form-field" style={{ gridColumn: 'span 2' }}>
                <label>Meaning</label>
                <input value={tf.meaning} onChange={e => setTf(p => ({ ...p, meaning: e.target.value }))}
                  placeholder='got beaten or outcompeted by someone who specifically wanted to beat you' required />
              </div>
              <div className="form-field">
                <label>Category</label>
                <select value={tf.category} onChange={e => setTf(p => ({ ...p, category: e.target.value }))}>
                  {TERM_CATS.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-field" style={{ gridColumn: 'span 2' }}>
                <label>Context (optional)</label>
                <input value={tf.context} onChange={e => setTf(p => ({ ...p, context: e.target.value }))}
                  placeholder='when to use it, tone, etc.' />
              </div>
              <div className="form-field" style={{ gridColumn: '1 / -1' }}>
                <label>Example sentences (one per line — the model learns from these)</label>
                <textarea rows={3} value={tf.examples} onChange={e => setTf(p => ({ ...p, examples: e.target.value }))}
                  placeholder={"I got tonyad in the hackathon bro\nbro completely tonyad me in the DSA round"} />
              </div>
            </div>
            <button className="btn primary" type="submit"><Plus size={13} /> Add term</button>
          </form>

          <div className="lex-list">
            {terms.length === 0 && <div className="dim" style={{ fontSize: 12 }}>No terms yet. Add your first one above.</div>}
            {terms.map(t => (
              <div key={t.id} className="lex-item">
                <div className="lex-item-header">
                  <span className="lex-term">{t.term}</span>
                  <span className={`tag ${CAT_COLORS[t.category] || 'gray'}`} style={{ fontSize: 10 }}>{t.category}</span>
                  <button className="btn ghost danger" style={{ padding: '2px 5px', marginLeft: 'auto' }}
                    onClick={() => deleteTerm(t.id)}><Trash2 size={11} /></button>
                </div>
                <div className="lex-meaning">{t.meaning}</div>
                {t.context && <div className="lex-context">[{t.context}]</div>}
                {t.examples.length > 0 && (
                  <div className="lex-examples">
                    {t.examples.map((ex, i) => (
                      <div key={i} className="lex-example">"{ex}"</div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Style rules ── */}
      {tab === 'style' && (
        <div className="lex-section">
          <form className="lex-form" onSubmit={addStyle}>
            <div className="form-row-3">
              <div className="form-field" style={{ gridColumn: 'span 2' }}>
                <label>Rule</label>
                <input value={sf.rule} onChange={e => setSf(p => ({ ...p, rule: e.target.value }))}
                  placeholder="Never say 'certainly' or 'absolutely' — sounds like a corporate bot" required />
              </div>
              <div className="form-field">
                <label>Category</label>
                <select value={sf.category} onChange={e => setSf(p => ({ ...p, category: e.target.value }))}>
                  {STYLE_CATS.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <button className="btn primary" type="submit"><Plus size={13} /> Add rule</button>
          </form>

          <div className="style-hints">
            <div className="dim" style={{ fontSize: 11, marginBottom: 8 }}>QUICK ADD EXAMPLES</div>
            {[
              ["Match my energy — casual gets casual, hype gets hype", "energy"],
              ["Never say 'certainly', 'absolutely', 'of course'", "forbidden"],
              ["I say 'bro' as neutral — use it back when natural", "address"],
              ["Be direct, no sugarcoating", "tone"],
              ["Don't over-explain things I clearly already know", "format"],
              ["When I'm venting, just listen — don't immediately problem-solve", "tone"],
            ].map(([rule, cat]) => (
              <button key={rule} className="hint-chip"
                onClick={() => setSf(p => ({ ...p, rule, category: cat }))}>
                + {rule}
              </button>
            ))}
          </div>

          <div className="lex-list">
            {rules.length === 0 && <div className="dim" style={{ fontSize: 12 }}>No style rules yet.</div>}
            {rules.map(r => (
              <div key={r.id} className="lex-item">
                <div className="lex-item-header">
                  <span className={`tag ${STYLE_COLORS[r.category] || 'gray'}`} style={{ fontSize: 10 }}>{r.category}</span>
                  <button className="btn ghost danger" style={{ padding: '2px 5px', marginLeft: 'auto' }}
                    onClick={() => deleteStyle(r.id)}><Trash2 size={11} /></button>
                </div>
                <div className="lex-meaning">{r.rule}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── References ── */}
      {tab === 'references' && (
        <div className="lex-section">
          <form className="lex-form" onSubmit={addRef}>
            <div className="form-row-3">
              <div className="form-field">
                <label>Trigger phrase</label>
                <input value={rf.trigger} onChange={e => setRf(p => ({ ...p, trigger: e.target.value }))}
                  placeholder='sigma grindset' required />
              </div>
              <div className="form-field" style={{ gridColumn: 'span 2' }}>
                <label>What it actually means</label>
                <input value={rf.meaning} onChange={e => setRf(p => ({ ...p, meaning: e.target.value }))}
                  placeholder="ironic reference to hustle culture — I don't mean it seriously" required />
              </div>
              <div className="form-field">
                <label>Ironic / sarcastic?</label>
                <select value={rf.is_ironic ? 'yes' : 'no'} onChange={e => setRf(p => ({ ...p, is_ironic: e.target.value === 'yes' }))}>
                  <option value="no">No — I mean it</option>
                  <option value="yes">Yes — I'm being ironic</option>
                </select>
              </div>
            </div>
            <button className="btn primary" type="submit"><Plus size={13} /> Add reference</button>
          </form>

          <div className="lex-list">
            {refs.length === 0 && <div className="dim" style={{ fontSize: 12 }}>No references yet. Add memes, inside jokes, cultural references.</div>}
            {refs.map(r => (
              <div key={r.id} className="lex-item">
                <div className="lex-item-header">
                  <span className="lex-term">{r.trigger}</span>
                  {r.is_ironic ? <span className="tag red" style={{ fontSize: 10 }}>ironic</span>
                               : <span className="tag green" style={{ fontSize: 10 }}>literal</span>}
                  <button className="btn ghost danger" style={{ padding: '2px 5px', marginLeft: 'auto' }}
                    onClick={() => deleteRef(r.id)}><Trash2 size={11} /></button>
                </div>
                <div className="lex-meaning">{r.meaning}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Preview ── */}
      {tab === 'preview' && (
        <div className="lex-section">
          <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 12 }}>
            This is exactly what gets injected into Hermes' system prompt before every response.
          </div>
          {preview ? (
            <pre className="preview-block">{preview}</pre>
          ) : (
            <div className="dim" style={{ fontSize: 12 }}>Click the Preview tab to load.</div>
          )}
        </div>
      )}
    </div>
  )
}
