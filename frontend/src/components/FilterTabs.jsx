import React from 'react';
import { Table, LayoutGrid } from 'lucide-react';

export default function FilterTabs({ statusFilter, setStatusFilter, viewMode, setViewMode }) {
  const tabs = [
    { key: 'ALL', label: 'All Jobs' },
    { key: 'APPLIED', label: 'Applied' },
    { key: 'ASSESSMENT', label: 'Assessment' },
    { key: 'INTERVIEW', label: 'Interview' },
    { key: 'OFFER_SELECTED', label: 'Offer' },
    { key: 'CLOSED', label: 'Closed / Rejected' },
  ];

  return (
    <div className="filter-section">
      <span className="filter-label">Status:</span>
      <div className="filter-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`filter-tab ${statusFilter === tab.key ? 'active' : ''}`}
            onClick={() => setStatusFilter(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* View Switcher: Table vs Kanban */}
      <div className="view-toggle">
        <button
          className={`view-toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
          onClick={() => setViewMode('table')}
        >
          <Table size={15} />
          <span>Table</span>
        </button>
        <button
          className={`view-toggle-btn ${viewMode === 'kanban' ? 'active' : ''}`}
          onClick={() => setViewMode('kanban')}
        >
          <LayoutGrid size={15} />
          <span>Kanban</span>
        </button>
      </div>
    </div>
  );
}
