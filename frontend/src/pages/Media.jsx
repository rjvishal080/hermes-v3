import { useState, useEffect } from 'react'
import { Film, BookOpen, Gamepad2, Tv, BookMarked, Star, Filter, TrendingUp, Search, ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import './Media.css'

const API = '/api/media'

const TYPE_ICONS = {
  movie:       Film,
  anime:       Tv,
  series:      Tv,
  manga:       BookOpen,
  manhwa:      BookOpen,
  manhua:      BookOpen,
  book:        BookOpen,
  novel:       BookOpen,
  light_novel: BookOpen,
  game:        Gamepad2,
  comic:       BookMarked,
  documentary: Film,
  podcast:     BookMarked,
}

const TYPE_COLORS = {
  movie: 'violet', anime: 'red', series: 'teal',
  manga: 'gold', manhwa: 'gold', manhua: 'gold',
  book: 'green', novel: 'green', light_novel: 'green',
  game: 'purple', comic: 'blue', documentary: 'gray',
}

const REWATCH_LABELS = {
  yes_definitely:         'Would rewatch',
  maybe:                  'Maybe rewatch',
  no_once_is_enough:      'Once is enough',
  carry_forever_no_rewatch: 'Carry forever',
  already_rewatched:      'Already rewatched',
}

const TRIGGERS = [
  { trigger: '@movie',  label: 'Movie' },
  { trigger: '@anime',  label: 'Anime' },
  { trigger: '@series', label: 'Series' },
  { trigger: '@manga',  label: 'Manga' },
  { trigger: '@book',   label: 'Book' },
  { trigger: '@game',   label: 'Game' },
]

export default function Media() {
  const [entries,   setEntries]  = useState([])
  const [stats,     setStats]    = useState(null)
  const [patterns,  setPatterns] = useState(null)
  const [filter,    setFilter]   = useState({ type: '', status: '', minRating: '' })
  const [search,    setSearch]   = useState('')
  const [selected,  setSelected] = useState(null)
  const [tab,       setTab]      = useState('library')
  const [loading,   setLoading]  = useState(false)

  useEffect(() => {
    fetchEntries()
    fetchStats()
  }, [filter])

  async function fetchEntries() {
    const params = new URLSearchParams()
    if (filter.type)      params.set('type', filter.type)
    if (filter.status)    params.set('status', filter.status)
    if (filter.minRating) params.set('min_rating', filter.minRating)
    const r = await fetch(`${API}?${params}`)
    const d = await r.json()
    setEntries(d.entries || [])
  }

  async function fetchStats() {
    const r = await fetch(`${API}/stats`)
    setStats(await r.json())
  }

  async function fetchPatterns() {
    setLoading(true)
    const r = await fetch(`${API}/patterns`)
    setPatterns(await r.json())
    setLoading(false)
  }

  async function deleteEntry(id) {
    await fetch(`${API}/${id}`, { method: 'DELETE' })
    fetchEntries(); fetchStats()
    if (selected?.id === id) setSelected(null)
  }

  const filtered = search
    ? entries.filter(e => e.title.toLowerCase().includes(search.toLowerCase()))
    : entries

  const types = stats ? Object.keys(stats.by_type || {}) : []

  return (
    <div className="page media-page">

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h1>Media Library</h1>
          <p>Log via chat: <span className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>@movie</span> <span className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>@anime</span> <span className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>@book</span> <span className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>@manga</span> <span className="mono" style={{ color: 'var(--accent)', fontSize: 12 }}>@game</span></p>
        </div>
        {stats && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <span className="tag blue">{stats.total} total</span>
            {stats.avg_rating && <span className="tag gold">avg {stats.avg_rating}/10</span>}
          </div>
        )}
      </div>

      {/* Trigger hint */}
      <div className="trigger-hint">
        <div className="trigger-hint-title">How to log in chat</div>
        <div className="trigger-examples">
          {TRIGGERS.map(t => (
            <div key={t.trigger} className="trigger-example">
              <span className="mono" style={{ color: 'var(--accent)' }}>{t.trigger}</span>
              <span style={{ color: 'var(--text3)' }}>I just finished [title]...</span>
            </div>
          ))}
        </div>
        <div className="trigger-note">Hermes will ask follow-up questions and store your interpretation, reaction, and personality signals automatically.</div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
        {[
          { id: 'library',  label: 'Library' },
          { id: 'patterns', label: 'Taste Profile' },
        ].map(t => (
          <button key={t.id}
            className={`tab-btn ${tab === t.id ? 'active' : ''}`}
            onClick={() => { setTab(t.id); if (t.id === 'patterns' && !patterns) fetchPatterns() }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Library tab */}
      {tab === 'library' && (
        <div className="library-layout">
          <div className="library-main">

            {/* Filters */}
            <div className="filter-bar">
              <div style={{ position: 'relative', flex: 1 }}>
                <Search size={12} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text3)' }} />
                <input value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="Search titles…"
                  style={{ paddingLeft: 28, fontSize: 12 }} />
              </div>
              <select value={filter.type} onChange={e => setFilter(p => ({ ...p, type: e.target.value }))} style={{ width: 'auto', fontSize: 12 }}>
                <option value="">All types</option>
                {['movie','anime','series','manga','book','game','comic','documentary'].map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <select value={filter.status} onChange={e => setFilter(p => ({ ...p, status: e.target.value }))} style={{ width: 'auto', fontSize: 12 }}>
                <option value="">All status</option>
                {['completed','watching','dropped','want_to','on_hold'].map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <select value={filter.minRating} onChange={e => setFilter(p => ({ ...p, minRating: e.target.value }))} style={{ width: 'auto', fontSize: 12 }}>
                <option value="">Any rating</option>
                <option value="9">9+</option>
                <option value="8">8+</option>
                <option value="7">7+</option>
              </select>
            </div>

            {/* Stats row */}
            {stats && types.length > 0 && (
              <div className="type-pills">
                {types.map(t => (
                  <button key={t} onClick={() => setFilter(p => ({ ...p, type: p.type === t ? '' : t }))}
                    className={`type-pill ${filter.type === t ? 'active' : ''}`}>
                    {t} <span>{stats.by_type[t]}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Entry list */}
            <div className="entry-list">
              {filtered.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text3)' }}>
                  <Film size={28} style={{ marginBottom: 10, opacity: .3 }} />
                  <div>No entries yet.</div>
                  <div style={{ fontSize: 12, marginTop: 6 }}>Type <span className="mono" style={{ color: 'var(--accent)' }}>@movie I just finished...</span> in chat to log your first entry.</div>
                </div>
              )}
              {filtered.map(entry => (
                <EntryRow key={entry.id} entry={entry}
                  isSelected={selected?.id === entry.id}
                  onClick={() => setSelected(selected?.id === entry.id ? null : entry)}
                  onDelete={() => deleteEntry(entry.id)}
                />
              ))}
            </div>
          </div>

          {/* Selected entry detail */}
          {selected && (
            <div className="entry-detail">
              <EntryDetail entry={selected} onClose={() => setSelected(null)} onDelete={() => deleteEntry(selected.id)} />
            </div>
          )}
        </div>
      )}

      {/* Patterns tab */}
      {tab === 'patterns' && (
        <div style={{ maxWidth: 600 }}>
          {loading && <div className="dim">Running pattern analysis…</div>}
          {!loading && !patterns && (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text3)' }}>
              <TrendingUp size={28} style={{ marginBottom: 10, opacity: .3 }} />
              <div>Need at least 5 completed entries for pattern analysis.</div>
              <button className="btn" style={{ marginTop: 12 }} onClick={fetchPatterns}>Run analysis</button>
            </div>
          )}
          {patterns && !patterns.error && <PatternsView data={patterns} />}
          {patterns?.error && <div className="dim">{patterns.error}</div>}
        </div>
      )}
    </div>
  )
}

function EntryRow({ entry, isSelected, onClick, onDelete }) {
  const Icon  = TYPE_ICONS[entry.type] || Film
  const color = TYPE_COLORS[entry.type] || 'gray'

  return (
    <div className={`entry-row ${isSelected ? 'selected' : ''}`} onClick={onClick}>
      <div className="entry-row-left">
        <span className={`tag ${color}`} style={{ fontSize: 10, padding: '1px 6px' }}>
          <Icon size={10} /> {entry.type}
        </span>
        <span className="entry-title">{entry.title}</span>
        {entry.creator && <span className="dim" style={{ fontSize: 11 }}>{entry.creator}</span>}
      </div>
      <div className="entry-row-right">
        {entry.rating && (
          <div className="rating-badge">
            <Star size={10} style={{ color: 'var(--gold)' }} />
            <span>{entry.rating}</span>
          </div>
        )}
        <span className="dim" style={{ fontSize: 10 }}>{entry.finished_date?.slice(0, 10) || ''}</span>
        <button className="btn ghost danger" style={{ padding: '2px 5px' }}
          onClick={e => { e.stopPropagation(); onDelete() }}><Trash2 size={11} /></button>
      </div>
    </div>
  )
}

function EntryDetail({ entry, onClose, onDelete }) {
  const Icon = TYPE_ICONS[entry.type] || Film

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
            <Icon size={14} style={{ color: 'var(--accent)' }} />
            <span style={{ fontWeight: 600, fontSize: 15 }}>{entry.title}</span>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {entry.year    && <span className="dim" style={{ fontSize: 11 }}>{entry.year}</span>}
            {entry.creator && <span className="dim" style={{ fontSize: 11 }}>· {entry.creator}</span>}
            {entry.rating  && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 11, color: 'var(--gold)' }}>
                · <Star size={10} /> {entry.rating}
              </span>
            )}
          </div>
        </div>
        <button className="btn ghost" style={{ fontSize: 11 }} onClick={onClose}>✕</button>
      </div>

      {entry.reaction && (
        <DetailBlock label="Reaction" text={entry.reaction} />
      )}
      {entry.interpretation && (
        <DetailBlock label="Interpretation" text={entry.interpretation} />
      )}
      {entry.what_worked?.length > 0 && (
        <TagBlock label="What worked" items={entry.what_worked} color="teal" />
      )}
      {entry.what_didnt?.length > 0 && (
        <TagBlock label="What didn't" items={entry.what_didnt} color="red" />
      )}
      {entry.themes_noticed?.length > 0 && (
        <TagBlock label="Themes" items={entry.themes_noticed} color="purple" />
      )}
      {entry.memorable_moments?.length > 0 && (
        <TagBlock label="Memorable moments" items={entry.memorable_moments} color="gold" />
      )}
      {entry.rewatch && (
        <div style={{ fontSize: 12 }}>
          <span className="dim">Rewatch: </span>
          <span style={{ color: 'var(--text)' }}>{REWATCH_LABELS[entry.rewatch] || entry.rewatch}</span>
        </div>
      )}
      {entry.recommendation && (
        <DetailBlock label="Recommend to" text={entry.recommendation} />
      )}
      {entry.personality_signals?.length > 0 && (
        <div>
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text3)', letterSpacing: '.5px', marginBottom: 5 }}>PERSONALITY SIGNALS EXTRACTED</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {entry.personality_signals.map((s, i) => (
              <div key={i} style={{ fontSize: 11, color: 'var(--accent)', padding: '2px 0' }}>· {s}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function DetailBlock({ label, text }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text3)', letterSpacing: '.5px', marginBottom: 4 }}>{label.toUpperCase()}</div>
      <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.65, fontStyle: 'italic' }}>"{text}"</div>
    </div>
  )
}

function TagBlock({ label, items, color }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text3)', letterSpacing: '.5px', marginBottom: 5 }}>{label.toUpperCase()}</div>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {items.map((item, i) => <span key={i} className={`tag ${color}`} style={{ fontSize: 10 }}>{item}</span>)}
      </div>
    </div>
  )
}

function PatternsView({ data }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {data.taste_profile && (
        <div className="card" style={{ borderColor: 'rgba(124,134,255,.25)' }}>
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--accent)', letterSpacing: '.5px', marginBottom: 8 }}>TASTE PROFILE</div>
          <div style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.7, fontStyle: 'italic' }}>"{data.taste_profile}"</div>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {data.what_they_love?.length > 0 && (
          <PatternCard label="What you love" items={data.what_they_love} color="teal" />
        )}
        {data.what_breaks_immersion?.length > 0 && (
          <PatternCard label="What breaks immersion" items={data.what_breaks_immersion} color="red" />
        )}
        {data.recurring_themes?.length > 0 && (
          <PatternCard label="Recurring themes" items={data.recurring_themes} color="purple" />
        )}
        {data.character_types_connected_with?.length > 0 && (
          <PatternCard label="Character types" items={data.character_types_connected_with} color="gold" />
        )}
      </div>
      {data.relationship_with_darkness && (
        <div className="card">
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text3)', marginBottom: 6 }}>RELATIONSHIP WITH DARKNESS</div>
          <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>{data.relationship_with_darkness}</div>
        </div>
      )}
      {data.analytical_style && (
        <div className="card">
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text3)', marginBottom: 6 }}>HOW YOU ENGAGE</div>
          <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>{data.analytical_style}</div>
          {data.emotional_engagement && <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 6, lineHeight: 1.6 }}>{data.emotional_engagement}</div>}
        </div>
      )}
    </div>
  )
}

function PatternCard({ label, items, color }) {
  return (
    <div className="card">
      <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text3)', letterSpacing: '.5px', marginBottom: 8 }}>{label.toUpperCase()}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {items.map((item, i) => (
          <div key={i} style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.5 }}>
            <span className={`tag ${color}`} style={{ fontSize: 9, marginRight: 5 }}>·</span>{item}
          </div>
        ))}
      </div>
    </div>
  )
}
