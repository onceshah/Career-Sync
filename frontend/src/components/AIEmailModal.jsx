import React, { useState } from 'react';
import { X, Sparkles, Copy, Check, Send } from 'lucide-react';

export default function AIEmailModal({ app, onClose }) {
  const [intent, setIntent] = useState('interview_confirm');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState(null);
  const [copied, setCopied] = useState(false);

  const generateDraft = async () => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/applications/${app.id}/draft-response`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intent, custom_notes: notes }),
      });
      if (res.ok) {
        const data = await res.json();
        setDraft(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (draft) {
      navigator.clipboard.writeText(`${draft.subject}\n\n${draft.draft_body}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!app) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <h2>AI Email Response Generator</h2>
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginTop: '2px' }}>
              Drafting response for <strong>{app.job_title}</strong> at <strong>{app.company_name}</strong>
            </p>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Intent Selectors */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155' }}>Select Response Intent:</label>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {[
              { id: 'interview_confirm', label: 'Confirm Interview' },
              { id: 'reschedule', label: 'Reschedule Request' },
              { id: 'follow_up', label: 'Status Follow-up' },
              { id: 'salary_inquiry', label: 'Discuss Offer' },
              { id: 'decline', label: 'Polite Decline' },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => setIntent(item.id)}
                style={{
                  padding: '0.45rem 0.85rem',
                  borderRadius: '9999px',
                  border: '1px solid #E2E8F0',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: intent === item.id ? '#4F75FF' : 'white',
                  color: intent === item.id ? 'white' : '#64748B',
                  borderColor: intent === item.id ? '#4F75FF' : '#E2E8F0'
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Custom Notes */}
        <div>
          <input 
            type="text"
            placeholder="Add custom candidate constraints (e.g. 'Available Tuesdays 2pm EST')"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #E2E8F0', outline: 'none', fontSize: '0.85rem' }}
          />
        </div>

        {/* Generate Button */}
        <button 
          onClick={generateDraft}
          disabled={loading}
          style={{
            background: 'linear-gradient(135deg, #4F75FF 0%, #3856E3 100%)',
            color: 'white',
            border: 'none',
            borderRadius: '9999px',
            padding: '0.75rem',
            fontWeight: 700,
            fontSize: '0.9rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem'
          }}
        >
          <Sparkles size={16} />
          <span>{loading ? 'Generating AI Response...' : 'Generate 1-Click Draft'}</span>
        </button>

        {/* Draft Display */}
        {draft && (
          <div style={{ background: '#F8FAFC', borderRadius: '16px', padding: '1.25rem', border: '1px solid #E2E8F0', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 800, fontSize: '0.88rem', color: '#0F172A' }}>{draft.subject}</span>
              <button 
                onClick={handleCopy}
                style={{ border: 'none', background: 'white', padding: '0.35rem 0.65rem', borderRadius: '6px', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 700, color: '#3856E3', border: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
              >
                {copied ? <Check size={14} color="#16A34A" /> : <Copy size={14} />}
                <span>{copied ? 'Copied!' : 'Copy Draft'}</span>
              </button>
            </div>

            <textarea 
              rows={8}
              readOnly
              value={draft.draft_body}
              style={{ width: '100%', background: 'white', border: '1px solid #CBD5E1', borderRadius: '8px', padding: '0.75rem', fontSize: '0.85rem', color: '#334155', resize: 'none' }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
