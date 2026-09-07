import { Routes, Route, NavLink } from 'react-router-dom'
import { MessageSquare, BarChart2, Brain, Database, Target, User, Zap, Cpu, BookMarked, Film } from 'lucide-react'
import Chat      from './pages/Chat'
import Dashboard from './pages/Dashboard'
import Memories  from './pages/Memories'
import Ingest    from './pages/Ingest'
import Goals     from './pages/Goals'
import Profile   from './pages/Profile'
import Models    from './pages/Models'
import Lexicon   from './pages/Lexicon'
import Media     from './pages/Media'
import './App.css'

const NAV = [
  { to: '/',          icon: MessageSquare, label: 'Chat'      },
  { to: '/dashboard', icon: BarChart2,     label: 'Dashboard' },
  { to: '/goals',     icon: Target,        label: 'Goals'     },
  { to: '/memories',  icon: Brain,         label: 'Memory'    },
  { to: '/media',     icon: Film,          label: 'Media'     },
  { to: '/lexicon',   icon: BookMarked,    label: 'Lexicon'   },
  { to: '/ingest',    icon: Database,      label: 'Data'      },
  { to: '/models',    icon: Cpu,           label: 'Models'    },
  { to: '/profile',   icon: User,          label: 'Profile'   },
]

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon"><Zap size={14} /></div>
          <span className="logo-text">Hermes</span>
          <span className="logo-version">v3</span>
        </div>
        <nav className="sidebar-nav">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Icon size={15} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="mono dim" style={{ fontSize: 10 }}>local · private</span>
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/"          element={<Chat />}      />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/goals"     element={<Goals />}     />
          <Route path="/memories"  element={<Memories />}  />
          <Route path="/media"     element={<Media />}     />
          <Route path="/lexicon"   element={<Lexicon />}   />
          <Route path="/ingest"    element={<Ingest />}    />
          <Route path="/models"    element={<Models />}    />
          <Route path="/profile"   element={<Profile />}   />
        </Routes>
      </main>
    </div>
  )
}
