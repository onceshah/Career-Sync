import React from 'react';
import { Search, Bell, ChevronDown } from 'lucide-react';

export default function Header({ searchQuery, setSearchQuery, reviewCount }) {
  return (
    <header className="top-header">
      <div className="header-title-section">
        <h1>Career Tracking Dashboard</h1>
        <p>Automated Intake, Presidio PII Protection & Local AI Job Intelligence</p>
      </div>

      <div className="header-actions">
        {/* Search Input */}
        <div className="search-box">
          <Search size={16} />
          <input 
            type="text" 
            placeholder="Search company, role..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {/* Bell Notification Badge */}
        <div className="icon-btn">
          <Bell size={18} />
          {reviewCount > 0 && <span className="notification-badge" />}
        </div>

        {/* User Profile Avatar */}
        <div className="user-avatar">
          <img 
            src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=120" 
            alt="User Avatar" 
          />
          <ChevronDown size={14} style={{ color: '#64748B' }} />
        </div>
      </div>
    </header>
  );
}
