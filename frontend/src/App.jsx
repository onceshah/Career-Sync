import React, { useState, useEffect } from 'react';
import './App.css';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import FilterTabs from './components/FilterTabs';
import TableView from './components/TableView';
import KanbanView from './components/KanbanView';
import ResumeRAGModal from './components/ResumeRAGModal';
import AIEmailModal from './components/AIEmailModal';
import CreateAppModal from './components/CreateAppModal';
import ReviewQueueModal from './components/ReviewQueueModal';

export default function App() {
  const [activeTab, setActiveTab] = useState('applications');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [viewMode, setViewMode] = useState('table');
  const [searchQuery, setSearchQuery] = useState('');

  const [applications, setApplications] = useState([]);
  const [reviewsCount, setReviewsCount] = useState(0);
  const [loading, setLoading] = useState(true);

  // Modals state
  const [selectedAppForRAG, setSelectedAppForRAG] = useState(null);
  const [selectedAppForAIDraft, setSelectedAppForAIDraft] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);

  useEffect(() => {
    fetchApplications();
    fetchReviewCount();
  }, []);

  const fetchApplications = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/applications');
      if (res.ok) {
        const data = await res.json();
        setApplications(data);
      }
    } catch (err) {
      console.error("Failed to fetch applications:", err);
      // Fallback sample data for preview if backend isn't live
      setApplications([
        { id: '07097', company_name: 'Batu / Google', job_title: 'Software Engineer', requisition_id: '07097', platform: 'LinkedIn', current_state: 'APPLIED', created_at: new Date().toISOString() },
        { id: '05597', company_name: 'Granit / Microsoft', job_title: 'Data Scientist', requisition_id: '05597', platform: 'Indeed', current_state: 'ASSESSMENT', created_at: new Date().toISOString() },
        { id: '97439', company_name: 'Apung / Amazon', job_title: 'Cloud Architect', requisition_id: '97439', platform: 'Workday', current_state: 'INTERVIEW', created_at: new Date().toISOString() },
        { id: '12779', company_name: 'Bata / Stripe', job_title: 'Fullstack Engineer', requisition_id: '12779', platform: 'Greenhouse', current_state: 'OFFER_SELECTED', created_at: new Date().toISOString() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const fetchReviewCount = async () => {
    try {
      const res = await fetch('http://localhost:8000/reviews');
      if (res.ok) {
        const data = await res.json();
        setReviewsCount(data.length);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Filtered applications
  const filteredApps = applications.filter((app) => {
    const matchesSearch = 
      app.company_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      app.job_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (app.requisition_id && app.requisition_id.toLowerCase().includes(searchQuery.toLowerCase()));

    if (statusFilter === 'ALL') return matchesSearch;
    if (statusFilter === 'CLOSED') return matchesSearch && app.current_state === 'REJECTED';
    return matchesSearch && app.current_state === statusFilter;
  });

  return (
    <div className="app-container">
      {/* Curved Electric Royal Blue Sidebar */}
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab}
        onOpenCreateModal={() => setShowCreateModal(true)}
        onOpenReviewModal={() => setShowReviewModal(true)}
      />

      {/* Main Content Workspace */}
      <main className="main-workspace">
        {/* Header */}
        <Header 
          searchQuery={searchQuery} 
          setSearchQuery={setSearchQuery} 
          reviewCount={reviewsCount}
        />

        {/* Status Filter Tabs (Reference Image match) */}
        <FilterTabs 
          statusFilter={statusFilter} 
          setStatusFilter={setStatusFilter}
          viewMode={viewMode}
          setViewMode={setViewMode}
        />

        {/* View Switcher: Table View (Reference Image) vs Kanban Board */}
        {viewMode === 'table' ? (
          <TableView 
            applications={filteredApps}
            onSelectAppForRAG={(app) => setSelectedAppForRAG(app)}
            onSelectAppForAIDraft={(app) => setSelectedAppForAIDraft(app)}
          />
        ) : (
          <KanbanView 
            applications={filteredApps}
            onSelectAppForRAG={(app) => setSelectedAppForRAG(app)}
            onSelectAppForAIDraft={(app) => setSelectedAppForAIDraft(app)}
          />
        )}
      </main>

      {/* Modals */}
      {selectedAppForRAG && (
        <ResumeRAGModal 
          app={selectedAppForRAG} 
          onClose={() => setSelectedAppForRAG(null)} 
        />
      )}

      {selectedAppForAIDraft && (
        <AIEmailModal 
          app={selectedAppForAIDraft} 
          onClose={() => setSelectedAppForAIDraft(null)} 
        />
      )}

      {showCreateModal && (
        <CreateAppModal 
          onClose={() => setShowCreateModal(false)}
          onCreated={fetchApplications}
        />
      )}

      {showReviewModal && (
        <ReviewQueueModal 
          onClose={() => setShowReviewModal(false)}
          onResolved={() => {
            fetchApplications();
            fetchReviewCount();
          }}
        />
      )}
    </div>
  );
}
