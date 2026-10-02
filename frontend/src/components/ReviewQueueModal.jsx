import React, { useState, useEffect } from 'react';
import { X, AlertCircle, CheckCircle, ShieldAlert } from 'lucide-react';

export default function ReviewQueueModal({ onClose, onResolved }) {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReviews();
  }, []);

  const fetchReviews = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/reviews');
      if (res.ok) {
        const data = await res.json();
        setReviews(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (appId, state) => {
    try {
      const res = await fetch(`http://localhost:8000/reviews/${appId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirmed_state: state, note: 'Confirmed by candidate UI' }),
      });
      if (res.ok) {
        fetchReviews();
        onResolved();
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#EA580C' }}>
              <AlertCircle size={22} />
              <span>Human Review Queue (NEEDS_REVIEW)</span>
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginTop: '2px' }}>
              Contradictory state transitions flagged by the deterministic state machine for candidate confirmation.
            </p>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#94A3B8' }}>Loading review queue...</div>
        ) : reviews.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2.5rem', color: '#16A34A', background: '#F0FDF4', borderRadius: '16px', border: '1px solid #BBF7D0' }}>
            <CheckCircle size={32} style={{ marginBottom: '0.5rem' }} />
            <div style={{ fontWeight: 800, fontSize: '1rem' }}>Queue Clean! No Flagged Items</div>
            <div style={{ fontSize: '0.85rem', color: '#166534', marginTop: '4px' }}>All email state transitions are fully verified and aligned.</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {reviews.map((app) => (
              <div key={app.id} style={{ background: '#FFF7ED', borderRadius: '14px', padding: '1.25rem', border: '1px solid #FFEDD5', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: '0.98rem', color: '#9A3412' }}>{app.job_title}</div>
                    <div style={{ fontSize: '0.85rem', color: '#C2410C', marginTop: '2px' }}>{app.company_name}</div>
                  </div>
                  <span style={{ background: '#FEE2E2', color: '#DC2626', padding: '0.25rem 0.65rem', borderRadius: '9999px', fontSize: '0.78rem', fontWeight: 800 }}>
                    CONTRADICTORY TRANSITION
                  </span>
                </div>

                <div style={{ fontSize: '0.85rem', color: '#7C2D12', background: 'white', padding: '0.75rem', borderRadius: '8px', border: '1px solid #FED7AA' }}>
                  State Machine Guard: Proposed event conflicts with current state <strong>{app.current_state}</strong>. Please confirm intended state:
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {['APPLIED', 'ASSESSMENT', 'INTERVIEW', 'OFFER_SELECTED', 'REJECTED'].map((st) => (
                    <button
                      key={st}
                      onClick={() => handleResolve(app.id, st)}
                      style={{
                        background: 'white',
                        border: '1px solid #FDBA74',
                        color: '#9A3412',
                        borderRadius: '9999px',
                        padding: '0.35rem 0.75rem',
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      Confirm {st}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
