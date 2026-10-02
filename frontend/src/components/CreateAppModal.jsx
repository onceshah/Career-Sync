import React, { useState } from 'react';
import { X, Plus, Building2, Briefcase, Hash } from 'lucide-react';

export default function CreateAppModal({ onClose, onCreated }) {
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [reqId, setReqId] = useState('');
  const [platform, setPlatform] = useState('LinkedIn');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!company.trim() || !role.trim()) return;
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/applications/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: company,
          job_title: role,
          requisition_id: reqId || null,
          platform: platform,
          initial_state: 'APPLIED',
        }),
      });

      if (res.ok) {
        onCreated();
        onClose();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>Add New Application</h2>
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginTop: '2px' }}>
              Track a new job opportunity manually into the ATS state machine
            </p>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '0.35rem' }}>Company Name *</label>
            <input 
              type="text" 
              required
              placeholder="e.g. Google, Microsoft, Stripe"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              style={{ width: '100%', padding: '0.75rem', borderRadius: '10px', border: '1px solid #CBD5E1', outline: 'none', fontSize: '0.9rem' }}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '0.35rem' }}>Job Title *</label>
            <input 
              type="text" 
              required
              placeholder="e.g. Software Engineer, Data Scientist"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              style={{ width: '100%', padding: '0.75rem', borderRadius: '10px', border: '1px solid #CBD5E1', outline: 'none', fontSize: '0.9rem' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '0.35rem' }}>Requisition ID (Optional)</label>
              <input 
                type="text" 
                placeholder="e.g. REQ-9842"
                value={reqId}
                onChange={(e) => setReqId(e.target.value)}
                style={{ width: '100%', padding: '0.75rem', borderRadius: '10px', border: '1px solid #CBD5E1', outline: 'none', fontSize: '0.9rem' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '0.35rem' }}>Platform</label>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                style={{ width: '100%', padding: '0.75rem', borderRadius: '10px', border: '1px solid #CBD5E1', outline: 'none', fontSize: '0.9rem', background: 'white' }}
              >
                <option value="LinkedIn">LinkedIn</option>
                <option value="Indeed">Indeed</option>
                <option value="Greenhouse">Greenhouse</option>
                <option value="Lever">Lever</option>
                <option value="Workday">Workday</option>
                <option value="Direct Referral">Direct Referral</option>
              </select>
            </div>
          </div>

          <button 
            type="submit"
            disabled={loading}
            style={{
              marginTop: '1rem',
              background: '#4F75FF',
              color: 'white',
              border: 'none',
              borderRadius: '9999px',
              padding: '0.85rem',
              fontWeight: 700,
              fontSize: '0.95rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              boxShadow: '0 4px 14px rgba(79, 117, 255, 0.3)'
            }}
          >
            <Plus size={18} />
            <span>{loading ? 'Adding Application...' : 'Create Application'}</span>
          </button>
        </form>
      </div>
    </div>
  );
}
