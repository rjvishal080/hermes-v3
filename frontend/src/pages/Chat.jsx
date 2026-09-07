import { useState, useRef, useEffect } from 'react'
import { Send, Sparkles, RefreshCw, Cpu, Wrench, ChevronDown, ChevronRight } from 'lucide-react'
import './Chat.css'

const API = '/api'

const SUGGESTIONS = [
  'Prepare me for tomorrow — what do I need to focus on?',
  'How are my goals progressing this week?',
  'Where is my money going?',
  'Which subjects need urgent attention?',
  'Give me a weekly reflection.',
  '@movie I just finished [title]…',
  '@anime I just finished [title]…',
]

export default function Chat() {
  const [sessions, setSessions]     = useState([])
  const [sessionId, setSessionId]   = useState(null)
  const [messages, setMessages]     = useState([])
  const [input, setInput]           = useState('')
  const [loading, setLoading]       = useState(false)
  const [modelStatus, setModelStatus] = useState('connecting')
  const [modelName, setModelName]   = useState('')
  const [extractToast, setExtractToast] = useState(null)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  useEffect(() => { fetchSessions(); pollModel() }, [])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function pollModel() {
    try {
      const r = await fetch(`${API}/health`)
      const d = await r.json()
      if (d.llm?.loaded) {
        setModelStatus('ready')
        setModelName(d.llm.model_id?.split('/').pop() || 'Hermes-3')
      } else {
        setModelStatus('loading')
        setModelName('loading…')
        setTimeout(pollModel, 4000)
      }
    } catch {
      setModelStatus('error')
      setTimeout(pollModel, 6000)
    }
  }

  async function fetchSessions() {
    try {
      const r = await fetch(`${API}/chat/sessions`)
      setSessions(await r.json())
    } catch {}
  }

  async function loadSession(sid) {
    setSessionId(sid)
    const r = await fetch(`${API}/chat/history/${sid}`)
    const d = await r.json()
    setMessages(d.map(m => ({ role: m.role, content: m.content })))
  }

  function newSession() {
    setSessionId(null)
    setMessages([])
    inputRef.current?.focus()
  }

  async function send() {
    if (!input.trim() || loading) return
    const msg = input.trim()
    setInput('')
    setLoading(true)

    const newMsgs   = [...messages, { role: 'user', content: msg }]
    setMessages(newMsgs)
    const assistIdx = newMsgs.length
    setMessages(p => [...p, { role: 'assistant', content: '', tools_used: [] }])

    try {
      const r = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, session_id: sessionId }),
      })

      const reader  = r.body.getReader()
      const decoder = new TextDecoder()
      let sid = sessionId, full = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        for (const line of decoder.decode(value).split('\n')) {
          if (!line.startsWith('data: ')) continue
          try {
            const d = JSON.parse(line.slice(6))
            if (d.token) {
              full += d.token
              setMessages(p => {
                const u = [...p]
                u[assistIdx] = { ...u[assistIdx], content: full }
                return u
              })
            }
            if (d.session_id) sid = d.session_id
            if (d.done && d.extracted) {
              const total = Object.values(d.extracted).reduce((a, b) => a + b, 0)
              if (total > 0) {
                setExtractToast({ type: 'memory', data: d.extracted })
                setTimeout(() => setExtractToast(null), 4000)
              }
            }
            if (d.done && d.media_logged) {
              setExtractToast({ type: 'media', signals: d.signals || 0 })
              setTimeout(() => setExtractToast(null), 5000)
            }
          } catch {}
        }
      }

      if (!sessionId) { setSessionId(sid); fetchSessions() }
    } catch {
      setMessages(p => {
        const u = [...p]
        u[assistIdx] = { role: 'assistant', content: 'Backend error. Is it running?' }
        return u
      })
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const statusColor = { connecting: 'var(--text3)', loading: 'var(--gold)', ready: 'var(--green)', error: 'var(--red)' }[modelStatus]
  const statusDot   = { connecting: '○', loading: '◌', ready: '●', error: '✕' }[modelStatus]

  return (
    <div className="chat-layout">
      <div className="chat-sidebar">
        <button className="btn" style={{ width: '100%', marginBottom: 6 }} onClick={newSession}>
          <RefreshCw size={12} /> New chat
        </button>
        <div className="session-list">
          {sessions.map(s => (
            <div key={s.session_id}
              className={`session-item ${s.session_id === sessionId ? 'active' : ''}`}
              onClick={() => loadSession(s.session_id)}>
              <div className="session-preview">{s.preview}</div>
              <div className="session-meta">{s.message_count}msg · {s.last_message?.slice(0, 10)}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="chat-main">
        {/* Status bar */}
        <div className="status-bar">
          <Cpu size={11} style={{ color: statusColor }} />
          <span style={{ color: statusColor, fontSize: 11 }}>{statusDot}</span>
          <span style={{ fontSize: 11, color: 'var(--text2)' }}>{modelName || 'Hermes-3'}</span>
          {modelStatus === 'loading' && <span className="dim" style={{ fontSize: 10 }}>loading into VRAM (~60s)</span>}
          <span style={{ marginLeft: 'auto', fontSize: 10 }} className="dim">ReAct planner · hybrid retrieval</span>
        </div>

        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">
              <Sparkles size={28} style={{ color: 'var(--accent)', opacity: .4 }} />
              <p>Hermes knows you. Ask anything.</p>
              <div className="suggestions">
                {SUGGESTIONS.map(s => (
                  <button key={s} className="suggestion" onClick={() => setInput(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <Message key={i} msg={msg} isLast={i === messages.length - 1} loading={loading} />
          ))}
          <div ref={bottomRef} />
        </div>

        {extractToast && (
          <div className="extract-toast">
            {extractToast.type === 'media' ? (
              <>
                <span className="tag green" style={{ fontSize: 10 }}>✦ media logged</span>
                {extractToast.signals > 0 && (
                  <span className="tag blue" style={{ fontSize: 10 }}>+{extractToast.signals} signals</span>
                )}
              </>
            ) : extractToast.type === 'memory' ? (
              Object.entries(extractToast.data || {}).map(([k, v]) => v > 0 && (
                <span key={k} className="tag green" style={{ fontSize: 10 }}>+{v} {k}</span>
              ))
            ) : (
              Object.entries(extractToast).map(([k, v]) => typeof v === 'number' && v > 0 && (
                <span key={k} className="tag green" style={{ fontSize: 10 }}>+{v} {k}</span>
              ))
            )}
          </div>
        )}

        <div className="input-area">
          <textarea ref={inputRef} value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder={modelStatus === 'loading' ? 'Models loading…' : 'Ask Hermes anything about your life…'}
            rows={1} className="chat-input" disabled={modelStatus === 'loading'} />
          <button className="send-btn" onClick={send} disabled={loading || !input.trim() || modelStatus === 'loading'}>
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}

function Message({ msg, isLast, loading }) {
  const [showTrace, setShowTrace] = useState(false)
  const isAssistant = msg.role === 'assistant'
  const isEmpty     = !msg.content && isLast && loading

  return (
    <div className={`message ${msg.role}`}>
      <div className="msg-role">{msg.role === 'user' ? 'You' : 'Hermes'}</div>
      <div className="msg-content">
        {isEmpty ? <span className="cursor">▋</span> : msg.content}
      </div>
      {isAssistant && msg.tools_used?.length > 0 && (
        <button className="trace-toggle" onClick={() => setShowTrace(p => !p)}>
          <Wrench size={10} /> {msg.tools_used.length} tools used
          {showTrace ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        </button>
      )}
      {showTrace && (
        <div className="trace">
          {msg.tools_used.map((t, i) => <span key={i} className="tag gray" style={{ fontSize: 10 }}>{t}</span>)}
        </div>
      )}
    </div>
  )
}
