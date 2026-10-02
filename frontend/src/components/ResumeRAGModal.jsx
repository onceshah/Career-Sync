import React, { useState, useEffect } from 'react';
import { X, Upload, CheckCircle2, AlertTriangle, FileText, Sparkles } from 'lucide-react';

export default function ResumeRAGModal({ app, onClose }) {
  const [loading, setLoading] = useState(false);
  const [compatibility, setCompatibility] = useState(null);
  const [resumeText, setResumeText] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState(false);

  useEffect(() => {
    if (app) {
      fetchCompatibility();
    }
  }, [app]);

  const fetchCompatibility = async () => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/applications/${app.id}/compatibility`);
      if (res.ok) {
        const data = await res.json();
        setCompatibility(data);
      }
    } catch (err) {
      console.error("Failed to fetch RAG compatibility", err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!resumeText.trim()) return;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('raw_text', resumeText);
      const res = await fetch('http://localhost:8000/api/resume/upload', {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        setUploadSuccess(true);
        fetchCompatibility();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (!app) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <h2>Resume RAG Matcher</h2>
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginTop: '2px' }}>
              Job-Fit Analysis for <strong>{app.job_title}</strong> at <strong>{app.company_name}</strong>
            </p>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Compatibility Gauge */}
        {compatibility && (
          <div 
            style={{ 
              background: 'linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%)',
              borderRadius: '16px',
              padding: '1.5rem',
              border: '1px solid #BBF7D0',
              display: 'flex',
              alignItems: 'center',
              gap: '1.5rem'
            }}
          >
            <div 
              style={{
                width: '75px',
                height: '75px',
                borderRadius: '50%',
                background: '#16A34A',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 900,
                fontSize: '1.4rem',
                boxShadow: '0 4px 14px rgba(22, 163, 74, 0.3)',
                flexShrink: 0
              }}
            >
              {compatibility.match_score}%
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: '1.1rem', color: '#14532D' }}>
                {compatibility.match_category}
              </div>
              <div style={{ fontSize: '0.88rem', color: '#166534', marginTop: '4px' }}>
                {compatibility.summary_analysis}
              </div>
            </div>
          </div>
        )}

        {/* Skills Breakdown */}
        {compatibility && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {/* Matching Skills */}
            <div style={{ background: '#F8FAFC', borderRadius: '12px', padding: '1rem', border: '1px solid #E2E8F0' }}>
              <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#16A34A', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem' }}>
                <CheckCircle2 size={16} />
                <span>Matching Skills ({compatibility.matching_skills.length})</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                {compatibility.matching_skills.map((s) => (
                  <span key={s} style={{ background: '#DCFCE7', color: '#15803D', padding: '0.25rem 0.55rem', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 600 }}>
                    {s}
                  </span>
                ))}
              </div>
            </div>

            {/* Missing Skills */}
            <div style={{ background: '#F8FAFC', borderRadius: '12px', padding: '1rem', border: '1px solid #E2E8F0' }}>
              <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#EA580C', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem' }}>
                <AlertTriangle size={16} />
                <span>Skills Gaps ({compatibility.missing_skills.length})</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                {compatibility.missing_skills.length === 0 ? (
                  <span style={{ fontSize: '0.82rem', color: '#64748B' }}>None! Perfect alignment.</span>
                ) : (
                  compatibility.missing_skills.map((s) => (
                    <span key={s} style={{ background: '#FFEDD5', color: '#C2410C', padding: '0.25rem 0.55rem', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 600 }}>
                      {s}
                    </span>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* Update Resume Section */}
        <div style={{ borderTop: '1px solid #F1F5F9', paddingTop: '1rem' }}>
          <h4 style={{ fontSize: '0.92rem', fontWeight: 700, marginBottom: '0.5rem' }}>Update Candidate Resume Text</h4>
          <textarea 
            rows={3}
            placeholder="Paste raw resume text or skills list to re-evaluate match score..."
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            style={{ width: '100%', padding: '0.75rem', borderRadius: '10px', border: '1px solid #E2E8F0', outline: 'none', fontSize: '0.85rem' }}
          />
          <button 
            onClick={handleUpload}
            style={{ 
              marginTop: '0.75rem',
              background: '#4F75FF', 
              color: 'white', 
              border: 'none', 
              borderRadius: '9999px',
              padding: '0.6rem 1.2rem',
              fontSize: '0.85rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <Upload size={15} />
            <span>Update Resume & Re-evaluate</span>
          </button>
        </div>
      </div>
    </div>
  );
}
