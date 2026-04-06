import React, { useState, useEffect, useRef } from 'react';
import '../Dashboard.css';

interface DashboardProps {
  onCommence: () => void;
  isLoading: boolean;
  loadingProgress: number;
  loadingMessage: string;
  showToast: (message: string, type?: 'error' | 'info') => void;

  jdText: string; setJdText: React.Dispatch<React.SetStateAction<string>>;
  jdFileName: string; setJdFileName: React.Dispatch<React.SetStateAction<string>>;
  jdFile: File | null; setJdFile: React.Dispatch<React.SetStateAction<File | null>>;
  jdLoading: boolean; setJdLoading: React.Dispatch<React.SetStateAction<boolean>>;
  jdProgress: number; setJdProgress: React.Dispatch<React.SetStateAction<number>>;
}

export const Dashboard: React.FC<DashboardProps> = ({
  onCommence,
  isLoading,
  loadingProgress,
  loadingMessage,
  showToast,
  jdText, setJdText,
  jdFileName, setJdFileName,
  jdFile, setJdFile,
  jdLoading, setJdLoading,
  jdProgress, setJdProgress
}) => {
  const [theme, setTheme] = useState<'Dark' | 'Light'>('Dark');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const jdInputRef = useRef<HTMLInputElement>(null);

  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const resp = await fetch('http://localhost:8000/api/interviews/');
        if (resp.ok) {
          const data = await resp.json();
          const sorted = data.sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          setHistory(sorted.map((item: any) => {
             // Try to extract a simple title from JD text
             let titleStr = item.jd_text ? item.jd_text.split('\n')[0].replace(/[^a-zA-Z0-9 ]/g, "").trim() : '';
             if (!titleStr || titleStr.length < 3) titleStr = "Interview Session";
             else if (titleStr.length > 30) titleStr = titleStr.substring(0, 30) + '...';
             
             return {
                 id: item.id,
                 title: titleStr,
                 time: new Date(item.created_at).toLocaleString(),
                 status: item.status || 'UNKNOWN'
             }
          }));
        }
      } catch (e) {
        console.error("Failed to fetch history", e);
      }
    };
    fetchHistory();
  }, []);

  // Listen for Cmd+K or Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
      if (e.key === 'Escape') {
        setIsSearchOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const simulateProgress = async (setter: React.Dispatch<React.SetStateAction<number>>, done: () => void) => {
    for (let i = 0; i <= 100; i += 10) {
      setter(i);
      await new Promise(r => setTimeout(r, 60 + Math.random() * 40));
    }
    done();
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setJdLoading(true);
    setJdProgress(0);
    await simulateProgress(setJdProgress, () => {
      setJdText(''); // Clear text when file is selected
      setJdFileName(file.name);
      setJdFile(file);
      setJdLoading(false);
    });
  };

  const handleCommence = () => {
    if (!jdText && !jdFile) {
      showToast('Please provide a Job Description.', 'error');
      return;
    }
    onCommence();
  };

  const filteredHistory = history.filter(item =>
    item.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="loading-overlay">
        <div className="loading-bar-container">
          <div
            className="loading-bar-fill"
            style={{ width: `${loadingProgress}%` }}
          />
        </div>
        <div className="loading-message">{loadingMessage}</div>
      </div>
    );
  }

  return (
    <div className={`dashboard-container ${theme === 'Light' ? 'light-theme' : ''}`}>
      {/* Search Modal */}
      {isSearchOpen && (
        <div className="search-modal-backdrop" onClick={() => setIsSearchOpen(false)}>
          <div className="search-modal-content" onClick={e => e.stopPropagation()}>
            <div className="search-modal-header">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input
                type="text"
                className="search-modal-input"
                placeholder="Search sessions..."
                autoFocus
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
            </div>
            <div className="search-modal-body">
              {filteredHistory.length > 0 ? (
                filteredHistory.map(item => (
                  <div key={item.id} className="search-result-item" onClick={() => {
                      setIsSearchOpen(false);
                      if (item.status === 'COMPLETED') {
                          window.open(`http://localhost:8000/api/interviews/${item.id}/pdf/`, '_blank');
                      } else {
                          showToast('This session is not completed yet.', 'info');
                      }
                  }} style={{ cursor: 'pointer' }}>
                    <div className="search-result-title">{item.title}</div>
                    <div className="search-result-meta">{item.time} • {item.status}</div>
                  </div>
                ))
              ) : (
                <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                  No results found for "{searchQuery}"
                </div>
              )}
            </div>
            <div className="search-modal-footer">
              <div className="search-hints">
                <span><span className="search-hint-key">Esc</span> to close</span>
                <span><span className="search-hint-key">↵</span> to select</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                {filteredHistory.length} sessions found
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-top">
          <button className="search-bar" onClick={() => setIsSearchOpen(true)} style={{ width: '100%', cursor: 'pointer', textAlign: 'left' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <span style={{ marginLeft: '8px', opacity: 0.5, flex: 1 }}>Search sessions...</span>
            <span style={{ fontSize: '0.7rem', opacity: 0.3, border: '1px solid currentColor', padding: '0 4px', borderRadius: '3px' }}>⌘K</span>
          </button>
          <button className="initiate-btn" onClick={() => { setJdText(''); setJdFile(null); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
            </svg>
            New Session
          </button>
        </div>

        <div className="sidebar-middle">
          <h2 className="section-title">Recent</h2>
          <div className="session-list">
            {history.map(session => (
              <div key={session.id} className="session-entry" onClick={() => {
                   if (session.status === 'COMPLETED') {
                       window.open(`http://localhost:8000/api/interviews/${session.id}/pdf/`, '_blank');
                   } else {
                       showToast('This session is not completed yet.', 'info');
                   }
                }}
                style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '4px' }}
              >
                <div className="session-title-text" style={{ fontWeight: 'bold' }}>{session.title}</div>
                <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>
                    {session.time.split(',')[0]} • {session.status}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="sidebar-bottom">
          <div
            className="theme-toggle sidebar-link"
            onClick={() => setTheme(prev => prev === 'Dark' ? 'Light' : 'Dark')}
          >
            <span>System Theme</span>
            <span style={{ color: 'var(--accent-purple)', fontWeight: 600 }}>{theme}</span>
          </div>
          <div className="sidebar-link">Configuration</div>
          <div className="sidebar-link">Help Resources</div>
          <div className="sidebar-link">Documentation</div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <div className="staging-view">
          <div className="module-container">
            <input
              type="file"
              ref={jdInputRef}
              style={{ display: 'none' }}
              accept=".txt,.md,.doc,.docx"
              onChange={handleFileUpload}
            />
            <div className={`upload-module ${(jdText || jdFile || jdLoading) ? 'active' : ''}`}>
              <div style={{ width: '100%', marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: (jdText || jdFile || jdLoading) ? 'var(--accent-purple)' : 'inherit' }}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                <h3 style={{ fontSize: '0.9rem', margin: 0 }}>{jdLoading ? 'Ingesting...' : (jdFileName || 'Job Description')}</h3>
              </div>

              {!jdFileName && !jdLoading && (
                <textarea
                  className="jd-textarea"
                  placeholder="Paste or type JD here..."
                  value={jdText}
                  onChange={(e) => {
                    setJdText(e.target.value);
                    setJdFile(null);
                    setJdProgress(0);
                  }}
                  onClick={e => e.stopPropagation()}
                />
              )}

              {!jdFileName && !jdText && !jdLoading && (
                <div className="upload-btn" onClick={() => jdInputRef.current?.click()}>
                  upload text file
                </div>
              )}

              {(jdFileName || jdText) && !jdLoading && (
                <div style={{ fontSize: '0.8rem', opacity: 0.6, cursor: 'pointer', marginBottom: '8px' }} onClick={() => { setJdText(''); setJdFileName(''); setJdFile(null); setJdProgress(0); }}>
                  Click to reset
                </div>
              )}

              {(jdLoading || jdFile) && (
                <div className="card-loading-bar-container static">
                  <div className="card-loading-bar-fill" style={{ width: `${jdLoading ? jdProgress : 100}%` }} />
                </div>
              )}
            </div>
          </div>

          <button className="commence-btn" onClick={handleCommence}>
            Commence Interview
          </button>
        </div>
      </main>
    </div>
  );
};
