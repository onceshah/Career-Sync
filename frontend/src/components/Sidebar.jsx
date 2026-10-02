import React, { useState } from 'react';
import { 
  Briefcase, 
  Layers, 
  FileText, 
  AlertCircle, 
  Calendar, 
  Sparkles, 
  Plus, 
  ChevronRight,
  User,
  Compass,
  MessageSquare
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, onOpenCreateModal, onOpenReviewModal }) {
  const [showSubMenu, setShowSubMenu] = useState(false);

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar-logo-container">
        <div className="sidebar-logo-icon">
          <Briefcase size={22} />
        </div>
        <span className="sidebar-logo-text">CareerSync</span>
      </div>

      {/* Add Application Button (+ Buat Order) */}
      <button className="sidebar-add-btn" onClick={onOpenCreateModal}>
        <Plus size={18} />
        <span>+ Add Application</span>
      </button>

      {/* Navigation List */}
      <nav className="sidebar-nav">
        {/* User Account / Profile */}
        <div className="nav-item">
          <User size={18} />
          <span>Candidate Profile</span>
        </div>

        {/* Regular Applications (Active Order Reguler Item from Reference UI) */}
        <div 
          className={`nav-item ${activeTab === 'applications' ? 'active' : ''}`}
          onClick={() => setActiveTab('applications')}
          onMouseEnter={() => setShowSubMenu(true)}
          onMouseLeave={() => setShowSubMenu(false)}
        >
          <Layers size={18} />
          <span>Applications</span>
          <ChevronRight size={16} style={{ marginLeft: 'auto', opacity: 0.7 }} />

          {/* SubMenu Popover matching Reference Image popover */}
          {showSubMenu && (
            <div className="nav-popover">
              <div className="nav-popover-item" onClick={() => setActiveTab('applications')}>
                All Active Jobs
              </div>
              <div className="nav-popover-item" onClick={() => setActiveTab('opportunities')}>
                Discovered Opportunities
              </div>
            </div>
          )}
        </div>

        {/* Resume RAG Matcher */}
        <div 
          className={`nav-item ${activeTab === 'resume' ? 'active' : ''}`}
          onClick={() => setActiveTab('resume')}
        >
          <FileText size={18} />
          <span>Resume RAG Matcher</span>
        </div>

        {/* Human Review Queue (NEEDS_REVIEW) */}
        <div 
          className={`nav-item ${activeTab === 'review' ? 'active' : ''}`}
          onClick={onOpenReviewModal}
        >
          <AlertCircle size={18} />
          <span>Review Queue</span>
        </div>

        {/* Calendar Events */}
        <div 
          className={`nav-item ${activeTab === 'calendar' ? 'active' : ''}`}
          onClick={() => setActiveTab('calendar')}
        >
          <Calendar size={18} />
          <span>Calendar HITL</span>
        </div>

        {/* AI Email Assistant */}
        <div 
          className={`nav-item ${activeTab === 'ai-draft' ? 'active' : ''}`}
          onClick={() => setActiveTab('ai-draft')}
        >
          <Sparkles size={18} />
          <span>AI Response Generator</span>
        </div>
      </nav>
    </aside>
  );
}
