import { useState, useEffect, useCallback } from 'react'

const API_URL = 'http://localhost:8000/api'

interface Question {
  id: number;
  question_text: string;
  sequence_order: number;
  type: string;
  status: string;
  user_answer: string;
  feedback_text: string;
  score: number;
}

interface Interview {
  id: string;
  jd_text: string;
  resume_text: string;
  status: string;
  created_at: string;
  final_report: {
    aggregate_score: number;
    summary_feedback: string;
    total_questions: number;
    evaluated_questions: number;
  } | null;
  questions: Question[];
}

function App() {
  const [interviews, setInterviews] = useState<Interview[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedInterview, setSelectedInterview] = useState<Interview | null>(null)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')

  const fetchInterviews = useCallback(async () => {
    try {
      const resp = await fetch(`${API_URL}/interviews/`)
      if (resp.ok) {
        const data = await resp.json()
        setInterviews(data)
      }
    } catch (err) {
      console.error('Failed to fetch interviews:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInterviews()
    const interval = setInterval(fetchInterviews, 10000) // Polling every 10s
    return () => clearInterval(interval)
  }, [fetchInterviews])

  const stats = {
    total: interviews.length,
    completed: interviews.filter(i => i.status === 'COMPLETED').length,
    inProgress: interviews.filter(i => i.status === 'IN_PROGRESS').length,
    pending: interviews.filter(i => i.status === 'PENDING').length,
    avgScore: interviews.reduce((acc, curr) => acc + (curr.final_report?.aggregate_score || 0), 0) / (interviews.filter(i => i.final_report).length || 1)
  }

  const scoreDistribution = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(score => ({
    label: score.toString(),
    count: interviews.filter(i => i.final_report && Math.round(i.final_report.aggregate_score) === score).length
  }))

  const maxCount = Math.max(...scoreDistribution.map(d => d.count), 1)

  return (
    <div className="admin-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <a href="#" className="sidebar-logo">INTERVIEW AI</a>
        <nav className="sidebar-nav">
          <a 
            href="#" 
            className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); setActiveTab('dashboard'); }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            Dashboard
          </a>
          <a 
            href="#" 
            className={`nav-item ${activeTab === 'interviews' ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); setActiveTab('interviews'); }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            Interviews
          </a>
          <a 
            href="#" 
            className={`nav-item ${activeTab === 'analytics' ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); setActiveTab('analytics'); }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
            Analytics
          </a>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <header className="header">
          <h1>{activeTab === 'dashboard' ? 'Admin Dashboard' : activeTab === 'interviews' ? 'Interview Monitoring' : 'Performance Analytics'}</h1>
          <button className="btn btn-primary" onClick={fetchInterviews}>Refresh Data</button>
        </header>

        {activeTab === 'dashboard' && (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <span className="stat-label">Total Interviews</span>
                <span className="stat-value">{stats.total}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Average Score</span>
                <span className="stat-value">{stats.avgScore.toFixed(1)}/10</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Live Sessions</span>
                <span className="stat-value" style={{ color: '#ef4444' }}>{stats.inProgress}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Completion Rate</span>
                <span className="stat-value">{((stats.completed / (stats.total || 1)) * 100).toFixed(0)}%</span>
              </div>
            </div>

            <div className="content-grid">
              <div className="card">
                <div className="card-header">
                  <h2>Recent Activity</h2>
                  <button className="btn btn-outline" onClick={() => setActiveTab('interviews')}>Manage All</button>
                </div>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Interview ID</th>
                        <th>Status</th>
                        <th>Progress</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {interviews.slice(0, 6).map(interview => (
                        <tr key={interview.id}>
                          <td>{new Date(interview.created_at).toLocaleDateString()}</td>
                          <td title={interview.id}>{interview.id.substring(0, 8)}...</td>
                          <td>
                            <span className={`status-badge status-${interview.status.toLowerCase().replace('_', '-')}`}>
                              {interview.status}
                            </span>
                          </td>
                          <td>
                            {interview.final_report ? 
                              `${interview.final_report.evaluated_questions}/${interview.final_report.total_questions}` : 
                              `${interview.questions?.filter(q => q.status !== 'PENDING').length || 0}/${interview.questions?.length || 0}`
                            }
                          </td>
                          <td>
                            <button className="btn btn-outline" onClick={() => setSelectedInterview(interview)}>
                              {interview.status === 'IN_PROGRESS' ? 'Monitor' : 'Review'}
                            </button>
                          </td>
                        </tr>
                      ))}
                      {interviews.length === 0 && (
                        <tr>
                          <td colSpan={5} className="empty-state">No sessions recorded yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="card">
                <div className="card-header">
                  <h2>Score Distribution</h2>
                </div>
                <div className="chart-placeholder">
                  <div className="bar-chart">
                    {scoreDistribution.map(d => (
                      <div 
                        key={d.label} 
                        className="bar" 
                        style={{ height: `${(d.count / maxCount) * 100}%` }}
                        title={`Score ${d.label}: ${d.count} candidates`}
                      >
                        <span className="bar-label">{d.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div style={{ marginTop: '20px', fontSize: '0.8rem', color: '#666', textAlign: 'center' }}>
                  Aggregate Score Breakdown (1-10)
                </div>
              </div>
            </div>
          </>
        )}

        {activeTab === 'interviews' && (
          <div className="card">
            <div className="card-header" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '1rem' }}>
              <h2>Interview Monitoring</h2>
              <div style={{ display: 'flex', gap: '1rem', width: '100%' }}>
                <input 
                  type="text" 
                  placeholder="Search by ID or content..." 
                  className="btn-outline" 
                  style={{ flex: 1, padding: '0.5rem 1rem', borderRadius: '6px' }}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <select 
                  className="btn-outline" 
                  style={{ padding: '0.5rem', borderRadius: '6px' }}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="ALL">All Statuses</option>
                  <option value="IN_PROGRESS">Live / In Progress</option>
                  <option value="COMPLETED">Completed</option>
                  <option value="PENDING">Pending</option>
                </select>
              </div>
            </div>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Started At</th>
                    <th>ID</th>
                    <th>Status</th>
                    <th>Questions</th>
                    <th>AI Score</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {interviews
                    .filter(i => statusFilter === 'ALL' || i.status === statusFilter)
                    .filter(i => i.id.includes(searchQuery) || i.jd_text.includes(searchQuery))
                    .map(interview => (
                    <tr key={interview.id}>
                      <td>{new Date(interview.created_at).toLocaleString()}</td>
                      <td title={interview.id}>{interview.id.substring(0, 12)}...</td>
                      <td>
                        <span className={`status-badge status-${interview.status.toLowerCase().replace('_', '-')}`}>
                          {interview.status === 'IN_PROGRESS' ? '● LIVE' : interview.status}
                        </span>
                      </td>
                      <td>{interview.questions?.length || 0}</td>
                      <td className="score-badge">
                        {interview.final_report ? `${interview.final_report.aggregate_score}/10` : '—'}
                      </td>
                      <td>
                        <button className="btn btn-primary" onClick={() => setSelectedInterview(interview)}>
                          {interview.status === 'IN_PROGRESS' ? 'Monitor Live' : 'Open Details'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && (
           <div className="card">
             <div className="empty-state">
               <h2>Platform Analytics</h2>
               <p>Real-time data visualization of interview metrics.</p>
               <div className="stats-grid" style={{ marginTop: '2rem' }}>
                 <div className="stat-card" style={{ border: '1px solid var(--primary-purple)' }}>
                   <span className="stat-label">Avg Questions/Session</span>
                   <span className="stat-value">11.0</span>
                 </div>
                 <div className="stat-card" style={{ border: '1px solid var(--primary-purple)' }}>
                   <span className="stat-label">System Health</span>
                   <span className="stat-value" style={{ color: '#10b981' }}>OPTIMAL</span>
                 </div>
                 <div className="stat-card" style={{ border: '1px solid var(--primary-purple)' }}>
                   <span className="stat-label">Active Users</span>
                   <span className="stat-value">{stats.inProgress}</span>
                 </div>
               </div>
               <button className="btn btn-primary" style={{ marginTop: '2rem' }} onClick={() => setActiveTab('dashboard')}>Back to Overview</button>
             </div>
           </div>
        )}
      </main>

      {/* Detail Modal */}
      {selectedInterview && (
        <div className="modal-overlay" onClick={() => setSelectedInterview(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h2>{selectedInterview.status === 'IN_PROGRESS' ? 'LIVE MONITORING' : 'Interview Session Review'}</h2>
                {selectedInterview.status === 'IN_PROGRESS' && <span className="status-badge" style={{ backgroundColor: '#fee2e2', color: '#ef4444', animation: 'pulse 2s infinite' }}>LIVE FEED</span>}
              </div>
              <button className="btn" onClick={() => setSelectedInterview(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="stats-grid" style={{ marginBottom: '1rem' }}>
                <div className="stat-card">
                  <span className="stat-label">Status</span>
                  <span className="stat-value" style={{ fontSize: '1.2rem' }}>{selectedInterview.status}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Aggregate Score</span>
                  <span className="stat-value" style={{ fontSize: '1.2rem' }}>
                    {selectedInterview.final_report?.aggregate_score || 'N/A'}/10
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Interviews Questions</span>
                  <span className="stat-value" style={{ fontSize: '1.2rem' }}>
                    {selectedInterview.final_report?.evaluated_questions || 0}/{selectedInterview.final_report?.total_questions || 0}
                  </span>
                </div>
              </div>

              <div className="detail-section">
                <h4>Job Description (First 1000 chars)</h4>
                <div className="text-preview">{selectedInterview.jd_text.substring(0, 1000)}...</div>
              </div>

              <div className="detail-section">
                <h4>Resume Content (First 1000 chars)</h4>
                <div className="text-preview">{selectedInterview.resume_text.substring(0, 1000)}...</div>
              </div>

              {selectedInterview.final_report?.summary_feedback && (
                <div className="detail-section">
                  <h4>Summary Feedback</h4>
                  <div className="text-preview" style={{ backgroundColor: 'var(--secondary-pale-purple)' }}>
                    {selectedInterview.final_report.summary_feedback}
                  </div>
                </div>
              )}

              <div className="detail-section">
                <h4>Question Breakdown</h4>
                <div className="questions-list">
                  {selectedInterview.questions?.map(q => (
                    <div key={q.id} className="question-item">
                      <div className="question-header">
                        <strong>Q{q.sequence_order}: {q.type}</strong>
                        <span className={`status-badge status-${q.status.toLowerCase()}`}>{q.status}</span>
                      </div>
                      <p>{q.question_text}</p>
                      {q.user_answer && (
                        <div style={{ marginTop: '0.5rem' }}>
                          <strong>Answer:</strong>
                          <p style={{ fontSize: '0.875rem' }}>{q.user_answer}</p>
                        </div>
                      )}
                      {q.feedback_text && (
                        <div className="feedback-text">
                          <strong>AI Feedback ({q.score}/10):</strong> {q.feedback_text}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
              <button className="btn btn-outline" onClick={() => window.open(`${API_URL}/interviews/${selectedInterview.id}/pdf/`, '_blank')}>
                Download PDF Report
              </button>
              <button className="btn btn-primary" onClick={() => setSelectedInterview(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
