import { useState, useEffect } from 'react'
import { Search, Trash2, Plus, Brain, Clock, Settings, GitBranch } from 'lucide-react'
import './Memories.css'

const API = '/api'

const TABS = [
  { id: 'search',     icon: Search,    label: 'Search' },
  { id: 'semantic',   icon: Brain,     label: 'Facts' },
  { id: 'episodic',   icon: Clock,     label: 'Events' },
  { id: 'procedural', icon: Settings,  label: 'Preferences' },
  { id: 'graph',      icon: GitBranch, label: 'Graph' },
]

export default function Memories() {
  const [tab,      setTab]     = useState('search')
  const [query,    setQuery]   = useState('')
  const [results,  setResults] = useState([])
  const [semantic, setSemantic] = useState([])
  const [episodic, setEpisodic] = useState([])
  const [procedural,setProc]  = useState([])
  const [graph,    setGraph]   = useState(null)
  const [newMem,   setNewMem]  = useState('')
  const [loading,  setLoading] = useState(false)

  useEffect(() => {
    if (tab === 'semantic')   fetchSemantic()
    if (tab === 'episodic')   fetchEpisodic()
    if (tab === 'procedural') fetchProcedural()
    if (tab === 'graph')      fetchGraph()
  }, [tab])

  async function fetchSemantic()   { const r = await fetch(`${API}/memory/semantic`);    setSemantic(await r.json()) }
  async function fetchEpisodic()   { const r = await fetch(`${API}/memory/episodic?days=60`); setEpisodic(await r.json()) }
  async function fetchProcedural() { const r = await fetch(`${API}/memory/procedural`);  setProc(await r.json()) }
  async function fetchGraph()      { const r = await fetch(`${API}/memory/graph`);        setGraph(await r.json()) }

  async function search() {
    if (!query.trim()) return
    setLoading(true)
    const r = await fetch(`${API}/memory/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    })
    const d = await r.json()
    setResults(d.results || [])
    setLoading(false)
  }

  async function addMemory() {
    if (!newMem.trim()) return
    await fetch(`${API}/memory/collection/memories/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    // simple: use query param
    const params = new URLSearchParams({ text: newMem, source: 'manual' })
    await fetch(`${API}/memory/collection/memories/add?${params}`, { method: 'POST' })
    setNewMem('')
  }

  async function deleteSemanticFact(key) {
    await fetch(`${API}/memory/semantic/${encodeURIComponent(key)}`, { method: 'DELETE' })
    fetchSemantic()
  }

  async function deleteEpisode(id) {
    await fetch(`${API}/memory/episodic/${id}`, { method: 'DELETE' })
    fetchEpisodic()
  }

  const emotionColor = { positive: 'green', negative: 'red', neutral: 'gray' }

  return (
    <div className="page memories-page">
      <div className="page-header">
        <h1>Memory</h1>
        <p>Semantic · Episodic · Procedural · Knowledge Graph</p>
      </div>

      <div className="mem-tabs">
        {TABS.map(t => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            <t.icon size={13} /> {t.label}
          </button>
        ))}
      </div>

      <div className="mem-body">

        {/* Search */}
        {tab === 'search' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="add-row">
              <input value={newMem} onChange={e => setNewMem(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addMemory()}
                placeholder="Add a memory manually…" />
              <button className="btn primary" onClick={addMemory}><Plus size={13} /></button>
            </div>
            <div className="search-row">
              <input value={query} onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && search()}
                placeholder="Search all memory (BM25 + semantic hybrid)…" />
              <button className="btn" onClick={search} disabled={loading}>
                <Search size={13} /> {loading ? 'Searching…' : 'Search'}
              </button>
            </div>
            {results.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div className="dim" style={{ fontSize: 11 }}>{results.length} results (reranked)</div>
                {results.map((r, i) => (
                  <div key={i} className="mem-item">
                    <div className="mem-text">{r.text}</div>
                    <div className="mem-meta">
                      <span className="tag gray" style={{ fontSize: 10 }}>{r.metadata?.source || 'memory'}</span>
                      {r.collection && <span className="tag blue" style={{ fontSize: 10 }}>{r.collection}</span>}
                      <span className="dim" style={{ fontSize: 10, marginLeft: 'auto' }}>{r.metadata?.timestamp?.slice(0, 10)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Semantic facts */}
        {tab === 'semantic' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>{semantic.length} structured facts</div>
            {semantic.map(f => (
              <div key={f.key} className="mem-item">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>{f.key}</span>
                  <span style={{ fontSize: 13, color: 'var(--text)' }}>{f.value}</span>
                </div>
                <div className="mem-meta">
                  <span className="tag blue" style={{ fontSize: 10 }}>{f.category}</span>
                  <span className="dim" style={{ fontSize: 10 }}>confidence: {(f.confidence * 100).toFixed(0)}%</span>
                  <span className="dim" style={{ fontSize: 10 }}>{f.source}</span>
                  <button className="btn ghost danger" style={{ padding: '1px 4px', marginLeft: 'auto' }}
                    onClick={() => deleteSemanticFact(f.key)}><Trash2 size={11} /></button>
                </div>
              </div>
            ))}
            {semantic.length === 0 && <div className="dim">No semantic facts yet. They're extracted automatically from conversations.</div>}
          </div>
        )}

        {/* Episodic events */}
        {tab === 'episodic' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>{episodic.length} events (last 60 days)</div>
            {episodic.map(ep => (
              <div key={ep.id} className="mem-item">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <span style={{ fontSize: 13 }}>{ep.summary}</span>
                  <button className="btn ghost danger" style={{ padding: '1px 4px', flexShrink: 0 }}
                    onClick={() => deleteEpisode(ep.id)}><Trash2 size={11} /></button>
                </div>
                {ep.detail && ep.detail !== ep.summary && (
                  <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>{ep.detail.slice(0, 120)}…</div>
                )}
                <div className="mem-meta">
                  <span className="dim" style={{ fontSize: 10 }}>{ep.date}</span>
                  <span className="tag gray" style={{ fontSize: 10 }}>{ep.category}</span>
                  <span className={`tag ${emotionColor[ep.emotion] || 'gray'}`} style={{ fontSize: 10 }}>{ep.emotion}</span>
                  {'★'.repeat(ep.importance) && <span className="dim" style={{ fontSize: 10 }}>{'★'.repeat(ep.importance)}</span>}
                </div>
              </div>
            ))}
            {episodic.length === 0 && <div className="dim">No episodes yet. Events are extracted from conversations automatically.</div>}
          </div>
        )}

        {/* Procedural preferences */}
        {tab === 'procedural' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>{procedural.length} learned preferences</div>
            {procedural.map(p => (
              <div key={p.id} className="mem-item">
                <div style={{ fontSize: 13 }}>• {p.description}</div>
                <div className="mem-meta">
                  <span className="tag purple" style={{ fontSize: 10 }}>{p.category}</span>
                  <div style={{ flex: 1, height: 3, background: 'var(--bg3)', borderRadius: 2, overflow: 'hidden', maxWidth: 80 }}>
                    <div style={{ height: '100%', width: `${p.strength * 100}%`, background: 'var(--purple)', borderRadius: 2 }} />
                  </div>
                  <span className="dim" style={{ fontSize: 10 }}>{(p.strength * 100).toFixed(0)}% strength</span>
                  <span className="dim" style={{ fontSize: 10 }}>{p.source}</span>
                </div>
              </div>
            ))}
            {procedural.length === 0 && <div className="dim">No preferences learned yet. Hermes picks these up from how you talk and what you ask.</div>}
          </div>
        )}

        {/* Knowledge graph */}
        {tab === 'graph' && graph && (
          <div>
            <div className="dim" style={{ fontSize: 11, marginBottom: 12 }}>
              {graph.stats?.entities || 0} entities · {graph.stats?.relations || 0} relations
            </div>
            <pre style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)', lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
              {graph.context}
            </pre>
          </div>
        )}

      </div>
    </div>
  )
}
