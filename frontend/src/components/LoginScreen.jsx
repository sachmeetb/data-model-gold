import { useState } from 'react'
import { BP } from '../theme'
import { Shield, Loader2, CheckCircle2 } from '../icons'

// Mock Accenture SSO gate — ported from the prototype. Demo only: no real auth
// happens; a valid @accenture.com email drops the user into the app.
export default function LoginScreen({ onSignIn }) {
  const [email, setEmail] = useState('')
  const [authState, setAuthState] = useState('idle') // idle | authenticating | success
  const [error, setError] = useState(null)

  const submit = () => {
    setError(null)
    const trimmed = (email || '').trim().toLowerCase()
    if (!trimmed.endsWith('@accenture.com')) {
      setError('Use your accenture.com corporate email.')
      return
    }
    setAuthState('authenticating')
    setTimeout(() => setAuthState('success'), 900)
    setTimeout(() => {
      const namePart = trimmed.split('@')[0].split('.')
        .map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' ')
      onSignIn({
        email: trimmed,
        name: namePart || 'Accenture User',
        initials: (namePart.split(' ').map(p => p[0]).join('') || 'AC').slice(0, 2).toUpperCase(),
      })
    }, 1700)
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: `radial-gradient(circle at 30% 0%, ${BP.greenLight} 0%, ${BP.panel} 50%, white 100%)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
    }}>
      <div className="flex" style={{ maxWidth: 880, width: '100%', boxShadow: '0 24px 60px rgba(0,0,0,0.10)', borderRadius: 14, overflow: 'hidden', background: 'white' }}>
        {/* Left — brand panel */}
        <div className="hidden md:flex" style={{
          flex: 1, background: `linear-gradient(160deg, ${BP.greenDeep} 0%, ${BP.greenDeeper} 100%)`,
          padding: '44px 36px', color: 'white', flexDirection: 'column', justifyContent: 'space-between', minHeight: 460,
        }}>
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex items-center justify-center"
                style={{ width: 36, height: 36, borderRadius: 8, background: BP.yellow, color: BP.greenDeepest, fontWeight: 800, fontSize: 14 }}>
                {'>'}
              </div>
              <div className="t-12 tracking-widest font-bold" style={{ color: 'rgba(255,255,255,0.65)' }}>DATA PRODUCT ASSISTANT</div>
            </div>
            <h1 style={{ fontSize: 28, lineHeight: 1.2, fontWeight: 700, marginTop: 28, letterSpacing: -0.3 }}>
              From a business question to a governed data product — in one conversation.
            </h1>
            <p style={{ marginTop: 16, color: 'rgba(255,255,255,0.78)', fontSize: 13.5, lineHeight: 1.55 }}>
              Sign in with your Accenture account to discover, design and build data products with the agentic platform.
            </p>
          </div>
          <div className="t-105" style={{ color: 'rgba(255,255,255,0.55)' }}>
            Accenture Agentic Platform · internal
          </div>
        </div>

        {/* Right — sign-in panel */}
        <div style={{ flex: 1, padding: '44px 40px', minWidth: 320 }}>
          <div className="t-11 font-bold tracking-widest" style={{ color: BP.textMuted }}>SIGN IN</div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: BP.text, marginTop: 6, letterSpacing: -0.2 }}>Welcome</h2>
          <p className="t-125" style={{ color: BP.textMuted, marginTop: 4 }}>
            Use your Accenture single sign-on (SSO) to continue.
          </p>

          <div style={{ marginTop: 24 }}>
            <label className="t-11 font-bold tracking-wider" style={{ color: BP.textMuted }}>CORPORATE EMAIL</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') submit() }}
              disabled={authState !== 'idle'}
              placeholder="first.last@accenture.com"
              className="w-full"
              style={{
                marginTop: 6, padding: '10px 12px',
                border: `1px solid ${error ? '#C9342A' : BP.border}`, borderRadius: 8,
                fontSize: 13.5, color: BP.text, outline: 'none',
                background: authState !== 'idle' ? BP.panel : 'white',
              }}
            />
            {error && <div className="t-105 mt-1" style={{ color: '#C9342A' }}>{error}</div>}

            <button
              onClick={submit}
              disabled={authState !== 'idle'}
              className="w-full flex items-center justify-center gap-2 font-semibold"
              style={{
                marginTop: 14, padding: '11px 14px',
                background: authState === 'success' ? BP.greenDark : BP.green,
                color: 'white', border: 'none', borderRadius: 8, fontSize: 13.5,
                cursor: authState === 'idle' ? 'pointer' : 'default', transition: 'background 200ms',
              }}
            >
              {authState === 'idle' && (<><Shield size={14} /> Sign in with Accenture SSO</>)}
              {authState === 'authenticating' && (<><Loader2 size={14} className="animate-spin" /> Authenticating…</>)}
              {authState === 'success' && (<><CheckCircle2 size={14} /> Welcome, redirecting…</>)}
            </button>

            <div className="flex items-center gap-2 mt-3 t-11" style={{ color: BP.textSubtle }}>
              <Shield size={11} color={BP.green} />
              <span>Routed via Microsoft Entra ID · MFA enforced</span>
            </div>
          </div>

          <div style={{ marginTop: 28, paddingTop: 18, borderTop: `1px dashed ${BP.border}` }}>
            <div className="t-105" style={{ color: BP.textMuted, lineHeight: 1.55 }}>
              Trouble signing in? Contact <b style={{ color: BP.greenDark }}>support@accenture.com</b> or open a ticket on the Accenture Service Desk.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
