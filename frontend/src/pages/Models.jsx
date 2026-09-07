import { useState, useEffect } from 'react'
import { Cpu, Zap, RefreshCw, Download } from 'lucide-react'

const API = '/api'

const MODELS = [
  { id: 'NousResearch/Hermes-3-Llama-3.1-8B', name: 'Hermes 3 (8B)', desc: 'Recommended. Best tool use, JSON output, agentic tasks.', vram: '~5.5GB', recommended: true },
  { id: 'Qwen/Qwen2.5-7B-Instruct',           name: 'Qwen 2.5 (7B)', desc: 'Best instruction following at 7B. Great JSON.',          vram: '~4.5GB' },
  { id: 'mistralai/Mistral-7B-Instruct-v0.3', name: 'Mistral 7B',    desc: 'Fast, light. Good for simpler queries.',                 vram: '~4.1GB' },
  { id: 'microsoft/Phi-3.5-mini-instruct',    name: 'Phi 3.5 Mini',  desc: 'Smallest option. ~2.5GB VRAM.',                         vram: '~2.5GB' },
]

export default function Models() {
  const [current, setCurrent] = useState(null)
  const [vram,    setVram]    = useState(null)
  const [switching, setSwitching] = useState(null)
  const [hfToken, setHfToken] = useState('')
  const [msg, setMsg] = useState('')

  useEffect(() => {
    fetchModel(); fetchVram()
    const iv = setInterval(fetchVram, 5000)
    return () => clearInterval(iv)
  }, [])

  async function fetchModel() {
    const r = await fetch(`${API}/chat/model`)
    setCurrent(await r.json())
  }

  async function fetchVram() {
    try {
      const r = await fetch(`${API}/models/vram`)
      setVram(await r.json())
    } catch {}
  }

  async function switchModel(id) {
    setSwitching(id)
    const r = await fetch(`${API}/models/switch`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: id }),
    })
    const d = await r.json()
    setSwitching(null)
    setMsg(d.message || d.error || '')
    fetchModel(); fetchVram()
  }

  async function hfLogin() {
    await fetch(`${API}/models/hf-login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: hfToken }),
    })
    setMsg('HuggingFace token saved')
    setHfToken('')
  }

  const vramPct = vram?.used_vram && vram?.total_vram
    ? (parseFloat(vram.used_vram) / parseFloat(vram.total_vram)) * 100 : 0

  return (
    <div className="page" style={{ maxWidth: 680, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-header">
        <h1>Models</h1>
        <p>LLM selection, VRAM monitor, HuggingFace access.</p>
      </div>

      {msg && <div style={{ background: 'rgba(78,204,163,.08)', border: '1px solid rgba(78,204,163,.2)', borderRadius: 8, padding: '8px 12px', fontSize: 13, color: 'var(--green)' }}>{msg}</div>}

      {/* VRAM */}
      {vram && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10, fontWeight: 600, fontSize: 13 }}>
            <Cpu size={14} style={{ color: 'var(--accent)' }} /> VRAM
          </div>
          {vram.gpu_name ? <>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>
              <span>{vram.gpu_name}</span>
              <span>{vram.used_vram} / {vram.total_vram}</span>
            </div>
            <div style={{ height: 7, background: 'var(--bg3)', borderRadius: 3, overflow: 'hidden', marginBottom: 6 }}>
              <div style={{ height: '100%', borderRadius: 3, width: `${vramPct}%`, transition: 'width .5s',
                background: vramPct > 85 ? 'var(--red)' : vramPct > 70 ? 'var(--gold)' : 'var(--accent)' }} />
            </div>
            <div style={{ fontSize: 11, color: 'var(--text3)' }}>Free: {vram.free_vram}</div>
          </> : <div style={{ fontSize: 13, color: 'var(--text2)' }}>{vram.vram_summary}</div>}
        </div>
      )}

      {/* Current */}
      {current?.loaded && (
        <div className="card" style={{ borderColor: 'rgba(124,134,255,.25)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6, fontWeight: 600, fontSize: 13 }}>
            <Zap size={13} style={{ color: 'var(--accent)' }} /> Active
          </div>
          <div style={{ fontSize: 13, fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{current.model_id}</div>
          <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>
            {current.parameters_B}B params · {current.device} · {current.vram}
          </div>
        </div>
      )}

      {/* Model list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {MODELS.map(m => {
          const isActive = current?.model_id === m.id
          return (
            <div key={m.id} className="card" style={{ borderColor: isActive ? 'rgba(124,134,255,.3)' : undefined }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{m.name}</span>
                    {m.recommended && <span className="tag green" style={{ fontSize: 10 }}>recommended</span>}
                    {isActive && <span className="tag blue" style={{ fontSize: 10 }}>active</span>}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 3 }}>{m.desc}</div>
                  <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text3)' }}>{m.id} · {m.vram}</div>
                </div>
                {!isActive && (
                  <button className="btn" style={{ fontSize: 12, flexShrink: 0 }} onClick={() => switchModel(m.id)} disabled={!!switching}>
                    {switching === m.id
                      ? <><RefreshCw size={12} style={{ animation: 'spin 1s linear infinite' }} /> Loading…</>
                      : <><Download size={12} /> Switch</>}
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* HF token */}
      <div className="card">
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>HuggingFace Token</div>
        <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 10 }}>Required for gated models (Llama 3.1). huggingface.co/settings/tokens</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input type="password" value={hfToken} onChange={e => setHfToken(e.target.value)} placeholder="hf_…" />
          <button className="btn" onClick={hfLogin} disabled={!hfToken}>Save</button>
        </div>
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}
