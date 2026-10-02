import React from 'react';
import { Sparkles, FileText, Calendar, Building2, CheckCircle } from 'lucide-react';

export default function KanbanView({ applications, onSelectAppForRAG, onSelectAppForAIDraft }) {
  const columns = [
    { key: 'APPLIED', title: 'Applied', color: '#3B82F6' },
    { key: 'ASSESSMENT', title: 'Assessment', color: '#F59E0B' },
    { key: 'INTERVIEW', title: 'Interview', color: '#10B981' },
    { key: 'OFFER_SELECTED', title: 'Offer', color: '#8B5CF6' },
    { key: 'REJECTED', title: 'Closed', color: '#EF4444' },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1.25rem' }}>
      {columns.map((col) => {
        const colApps = applications.filter((a) => a.current_state === col.key);
        return (
          <div 
            key={col.key}
            style={{
              background: '#F8FAFC',
              borderRadius: '16px',
              padding: '1.25rem 1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
              border: '1px solid #E2E8F0',
              minHeight: '450px'
            }}
          >
            {/* Column Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: col.color }} />
                <span style={{ fontWeight: 800, fontSize: '0.92rem', color: '#0F172A' }}>{col.title}</span>
              </div>
              <span style={{ background: '#E2E8F0', color: '#475569', borderRadius: '9999px', padding: '0.15rem 0.6rem', fontSize: '0.78rem', fontWeight: 700 }}>
                {colApps.length}
              </span>
            </div>

            {/* Application Cards */}
            {colApps.map((app) => (
              <div 
                key={app.id}
                style={{
                  background: 'white',
                  borderRadius: '12px',
                  padding: '1rem',
                  boxShadow: '0 2px 8px rgba(148, 163, 184, 0.08)',
                  border: '1px solid #F1F5F9',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                  cursor: 'pointer'
                }}
              >
                <div style={{ fontWeight: 800, fontSize: '0.92rem', color: '#0F172A' }}>
                  {app.job_title}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#64748B', fontSize: '0.82rem' }}>
                  <Building2 size={14} />
                  <span>{app.company_name}</span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.25rem' }}>
                  <span style={{ fontSize: '0.75rem', color: '#16A34A', background: '#F0FDF4', padding: '0.25rem 0.5rem', borderRadius: '9999px', fontWeight: 700 }}>
                    88% Match
                  </span>
                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    <button 
                      onClick={() => onSelectAppForRAG(app)}
                      style={{ border: 'none', background: '#F1F5F9', borderRadius: '6px', padding: '0.35rem', cursor: 'pointer', color: '#475569' }}
                      title="RAG Compatibility"
                    >
                      <FileText size={14} />
                    </button>
                    <button 
                      onClick={() => onSelectAppForAIDraft(app)}
                      style={{ border: 'none', background: '#EFF6FF', borderRadius: '6px', padding: '0.35rem', cursor: 'pointer', color: '#2563EB' }}
                      title="AI Email Draft"
                    >
                      <Sparkles size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
