import React from 'react';
import { ArrowRight, Sparkles, FileText, ChevronRight, CheckCircle2 } from 'lucide-react';

export default function TableView({ applications, onSelectAppForRAG, onSelectAppForAIDraft }) {
  const getStatusBadge = (state) => {
    switch (state) {
      case 'APPLIED':
        return <span className="status-pill applied">Applied</span>;
      case 'ASSESSMENT':
        return <span className="status-pill assessment">Assessment</span>;
      case 'INTERVIEW':
        return <span className="status-pill interview">Interview</span>;
      case 'OFFER_SELECTED':
        return <span className="status-pill offer">Offer</span>;
      case 'REJECTED':
        return <span className="status-pill rejected">Rejected</span>;
      default:
        return <span className="status-pill review">{state}</span>;
    }
  };

  return (
    <div className="table-card-wrapper animate-fade-in">
      <table className="custom-table">
        <thead>
          <tr className="table-header-row">
            <th>Req ID</th>
            <th>Role & Company</th>
            <th>RAG Match</th>
            <th>Platform / Date</th>
            <th>Status Order</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {applications.length === 0 ? (
            <tr>
              <td colSpan={6} style={{ textAlign: 'center', padding: '3rem', color: '#94A3B8' }}>
                No active applications found. Click "+ Add Application" to create one.
              </td>
            </tr>
          ) : (
            applications.map((app) => (
              <tr key={app.id} className="table-body-row">
                {/* Req ID */}
                <td>{app.requisition_id || app.id.substring(0, 8)}</td>

                {/* Role & Company */}
                <td>
                  <div style={{ fontWeight: 700, color: '#0F172A', fontSize: '0.95rem' }}>
                    {app.job_title}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#64748B', marginTop: '2px' }}>
                    {app.company_name}
                  </div>
                </td>

                {/* RAG Score Badge */}
                <td>
                  <div 
                    onClick={() => onSelectAppForRAG(app)}
                    style={{ 
                      display: 'inline-flex', 
                      alignItems: 'center', 
                      gap: '0.4rem',
                      background: '#F0FDF4', 
                      color: '#16A34A',
                      padding: '0.35rem 0.75rem', 
                      borderRadius: '9999px',
                      fontSize: '0.82rem',
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    <CheckCircle2 size={14} />
                    <span>88% Match</span>
                  </div>
                </td>

                {/* Platform / Date */}
                <td>
                  <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#334155' }}>
                    {app.platform || 'Gmail Ingest'}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
                    {new Date(app.created_at || Date.now()).toLocaleDateString()}
                  </div>
                </td>

                {/* Status Order Badge */}
                <td>{getStatusBadge(app.current_state)}</td>

                {/* Orange Action Pill Button (Exact Reference Match: "Lacak Order >") */}
                <td>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <button 
                      className="btn-orange-action"
                      onClick={() => onSelectAppForRAG(app)}
                    >
                      <span>RAG Match</span>
                      <ChevronRight size={15} />
                    </button>

                    <button 
                      onClick={() => onSelectAppForAIDraft(app)}
                      style={{
                        background: '#F1F5F9',
                        border: 'none',
                        borderRadius: '9999px',
                        padding: '0.55rem 0.85rem',
                        fontSize: '0.82rem',
                        fontWeight: 700,
                        color: '#3856E3',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.35rem'
                      }}
                    >
                      <Sparkles size={14} />
                      <span>AI Reply</span>
                    </button>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
