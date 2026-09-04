/* eslint-disable */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import type { DailyCenterPlan } from '../types/auth';
import { DeliveryStatusPanel } from './DeliveryStatusPanel';
import './ClerkDashboard.css';

// ─── Live Report data types ───────────────────────────────────────────────────
interface LiveCenterData {
  center_id: number;
  center_name: string;
  category: string;
  tokens_distributed: number;
  quantity_filled_tons: number;
  limit_tons: number;
  fill_percent: number;
}

interface LiveReportData {
  date: string;
  tons_per_token_estimate: number;
  centers: LiveCenterData[];
  totals: {
    total_tokens: number;
    total_filled_tons: number;
    total_limit_tons: number;
    total_fill_percent: number;
  };
}

const DEFAULT_CENTERS: DailyCenterPlan[] = [
  { center_id: 1, center_name: 'Center 1 - North Cereals Hub', category: 'Cereals', limit_tons: 500 },
  { center_id: 2, center_name: 'Center 2 - Central Grain Silo', category: 'Cereals', limit_tons: 450 },
  { center_id: 3, center_name: 'Center 3 - East Pulse Depot', category: 'Pulses', limit_tons: 300 },
  { center_id: 4, center_name: 'Center 4 - South Legume Yard', category: 'Pulses', limit_tons: 250 },
  { center_id: 5, center_name: 'Center 5 - West Gram Storage', category: 'Pulses', limit_tons: 200 },
];

export const ClerkDashboard: React.FC = () => {
  const { user, logout } = useAuth();

  const [activeTab, setActiveTab] = useState<'planner' | 'live' | 'status'>('planner');
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('app-theme') as 'dark' | 'light') || 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('app-theme', theme);
  }, [theme]);



  // Date selection state for Procurement Planner (YYYY-MM-DD)
  const todayStr = new Date().toISOString().split('T')[0];
  const [selectedDate, setSelectedDate] = useState<string>(todayStr);
  const [plans, setPlans] = useState<DailyCenterPlan[]>(DEFAULT_CENTERS);
  const [isSavedInDb, setIsSavedInDb] = useState<boolean>(false);
  const [copiedFromDate, setCopiedFromDate] = useState<string | null>(null);

  // Status & Feedback states
  const [loading, setLoading] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  // Live Report state
  const [liveData, setLiveData] = useState<LiveReportData | null>(null);
  const [liveLoading, setLiveLoading] = useState<boolean>(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const liveIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch saved plan from backend for selected date
  const fetchPlanForDate = useCallback(async (dateToFetch: string) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`/api/procurement-plan?date=${dateToFetch}`);
      if (!res.ok) {
        throw new Error(`Failed to fetch plan (HTTP ${res.status})`);
      }
      const data = await res.json();
      if (data.plans && data.plans.length > 0) {
        setPlans(data.plans);
      } else {
        setPlans(DEFAULT_CENTERS);
      }
      setIsSavedInDb(!!data.is_saved);
      setCopiedFromDate(data.copied_from_date || null);
    } catch (err: any) {
      console.warn('Backend fetch /api/procurement-plan warning:', err);
      setPlans(DEFAULT_CENTERS);
      setFeedback({
        type: 'info',
        message: 'Loaded default center values (Backend offline or initializing).',
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlanForDate(selectedDate);
  }, [selectedDate, fetchPlanForDate]);

  // ── Live Report data fetch ──────────────────────────────────────────────────
  const fetchLiveReport = useCallback(async (isManual = false) => {
    if (isManual) setIsRefreshing(true);
    else if (!liveData) setLiveLoading(true);
    setLiveError(null);
    try {
      const res = await fetch('/api/live-report');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: LiveReportData = await res.json();
      setLiveData(data);
      setLastUpdated(new Date());
    } catch (err: any) {
      setLiveError(err.message || 'Network error — is the backend running?');
    } finally {
      setLiveLoading(false);
      setIsRefreshing(false);
    }
  }, [liveData]);

  // Start polling when Live tab is active; stop when leaving
  useEffect(() => {
    if (activeTab === 'live') {
      fetchLiveReport();
      liveIntervalRef.current = setInterval(() => fetchLiveReport(), 30_000);
    } else {
      if (liveIntervalRef.current) {
        clearInterval(liveIntervalRef.current);
        liveIntervalRef.current = null;
      }
    }
    return () => {
      if (liveIntervalRef.current) clearInterval(liveIntervalRef.current);
    };
  }, [activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle editing limit tons for a single center
  const handleLimitChange = (centerId: number, value: number) => {
    const numericVal = Math.max(0, isNaN(value) ? 0 : value);
    setPlans((prev) =>
      prev.map((item) =>
        item.center_id === centerId ? { ...item, limit_tons: numericVal } : item
      )
    );
  };

  // Submit day plan to backend
  const handleSubmitPlan = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFeedback(null);

    try {
      const res = await fetch('/api/procurement-plan', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          date: selectedDate,
          plans: plans,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      setIsSavedInDb(true);
      setCopiedFromDate(null);
      setFeedback({
        type: 'success',
        message: data.message || `Procurement plan for ${selectedDate} saved successfully!`,
      });
    } catch (err: any) {
      console.error('Error submitting plan:', err);
      setFeedback({
        type: 'error',
        message: `Failed to save plan: ${err.message || 'Network error'}. Check FastAPI backend.`,
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Calculations for summary stats
  const cerealsTotal = plans
    .filter((p) => p.category.toLowerCase() === 'cereals')
    .reduce((acc, p) => acc + p.limit_tons, 0);

  const pulsesTotal = plans
    .filter((p) => p.category.toLowerCase() === 'pulses')
    .reduce((acc, p) => acc + p.limit_tons, 0);

  const totalLimitTons = plans.reduce((acc, p) => acc + p.limit_tons, 0);

  // Quick date change handlers

  const formatDateToDDMMYYYY = (isoDate: string) => {
    if (!isoDate) return '';
    const parts = isoDate.split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return isoDate;
  };

  const handleQuickDate = (offsetDays: number) => {

    const d = new Date(selectedDate || todayStr);
    d.setDate(d.getDate() + offsetDays);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  return (
    <div className="clerk-app-layout">
      {/* Mobile Drawer Overlay */}
      {sidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Side Navigation Panel */}
      <aside className={`side-nav-panel ${sidebarOpen ? 'mobile-open' : ''}`}>
        <div className="side-nav-header">
          <div className="brand-badge">
            <span className="brand-icon"></span>
            <div className="brand-text">
              <span className="brand-title">MandiMitra</span>
              <span className="brand-sub">Clerk Portal</span>
            </div>
          </div>
          <button
            type="button"
            className="mobile-close-btn"
            onClick={() => setSidebarOpen(false)}
          >
            
          </button>
        </div>

        <div className="user-profile-card">
          <div className="user-avatar">
            {(user?.name || user?.username || 'C').charAt(0).toUpperCase()}
          </div>
          <div className="user-details">
            <div className="user-name-text">{user?.name || user?.username}</div>
            <div className="user-role-badge">Govt Agri Clerk</div>
          </div>
        </div>

        <nav className="side-nav-menu">
          <div className="nav-group-label">NAVIGATION</div>

          <button
            type="button"
            className={`nav-item-btn ${activeTab === 'planner' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('planner');
              setSidebarOpen(false);
            }}
          >
            <span className="nav-icon"></span>
            <div className="nav-label-container">
              <span className="nav-title">The Procurement Planner</span>
              <span className="nav-subtitle">Daily limit allocation</span>
            </div>
          </button>

          <button
            type="button"
            className={`nav-item-btn ${activeTab === 'live' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('live');
              setSidebarOpen(false);
            }}
          >
            <span className="nav-icon"></span>
            <div className="nav-label-container">
              <span className="nav-title">The Live Report</span>
              <span className="nav-subtitle">Token & capacity metrics</span>
            </div>
          </button>

          <button
            type="button"
            className={`nav-item-btn ${activeTab === 'status' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('status');
              setSidebarOpen(false);
            }}
          >
            <span className="nav-icon"></span>
            <div className="nav-label-container">
              <span className="nav-title">Token Status</span>
              <span className="nav-subtitle">Gate & delivery updates</span>
            </div>
          </button>
        </nav>


        <div className="side-nav-footer">
          <button type="button" className="sidebar-logout-btn" onClick={logout}>
            <span></span> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="main-content-wrapper">
        {/* Top Bar Navigation Header */}
        <header className="top-nav-bar">
          <div className="top-bar-left">
            <button
              type="button"
              className="hamburger-menu-btn"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              title="Toggle Menu"
            >
              
            </button>
            <div className="current-page-title">
              {activeTab === 'planner' ? 'The Procurement Planner' : activeTab === 'live' ? 'The Live Report' : 'Token Status'}
            </div>
          </div>


          <div className="top-bar-right">
            <button 
              type="button" 
              className="theme-toggle-btn" 
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              title="Toggle Theme"
            >
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
            <span className="role-chip">Role: govt-agri-clerk</span>

            <button type="button" className="top-logout-btn" onClick={logout}>
              Sign Out
            </button>
          </div>
        </header>

        {/* Page 1: The Procurement Planner */}
        {activeTab === 'planner' && (
          <main className="page-container planner-page">
            <div className="page-header-section">
              <div>
                <h1 className="page-main-title">The Procurement Planner</h1>
                <p className="page-description">
                  Configure daily procurement capacity limits for 5 government centers (2 Cereals, 3 Pulses).
                </p>
              </div>

              {/* Date Selection Box */}
              <div className="date-picker-box">
                <label htmlFor="procurement-date-input" className="date-picker-label">
                   Target Planning Date:
                </label>
                <div className="date-picker-controls">
                  <button
                    type="button"
                    className="date-nav-btn"
                    onClick={() => handleQuickDate(-1)}
                    title="Previous Day"
                  >
                    ◀
                  </button>
                  <div className="date-input-wrapper" style={{ position: 'relative', display: 'inline-block' }}>
                    <div className="date-input" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', minWidth: '140px', cursor: 'pointer' }}>
                      <span>{formatDateToDDMMYYYY(selectedDate)}</span>
                      <span style={{ fontSize: '1.1rem' }}></span>
                    </div>
                    <input
                      id="procurement-date-input"
                      type="date"
                      value={selectedDate}
                      onChange={(e) => setSelectedDate(e.target.value)}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '100%',
                        opacity: 0,
                        cursor: 'pointer'
                      }}
                    />
                  </div>
                  <button
                    type="button"
                    className="date-nav-btn"
                    onClick={() => handleQuickDate(1)}
                    title="Next Day"
                  >
                    ▶
                  </button>
                  <button
                    type="button"
                    className="today-quick-btn"
                    onClick={() => setSelectedDate(todayStr)}
                  >
                    Today
                  </button>
                </div>
              </div>
            </div>

            {/* Persistence Sync Banner */}
            <div className="status-sync-bar">
              {loading ? (
                <span className="sync-status loading"> Fetching plan from backend...</span>
              ) : isSavedInDb ? (
                <span className="sync-status saved">
                   Saved Plan: Showing limits stored in backend for <strong>{formatDateToDDMMYYYY(selectedDate)}</strong>.
                </span>
              ) : copiedFromDate ? (
                <span className="sync-status copied">
                   Auto-Prepopulated: Showing limits remembered from previous plan (<strong>{copiedFromDate ? formatDateToDDMMYYYY(copiedFromDate) : ''}</strong>). Submit to save for <strong>{formatDateToDDMMYYYY(selectedDate)}</strong>.
                </span>
              ) : (
                <span className="sync-status initial">
                  ℹ️ Example Plan: Showing initial example limits. Edit and submit to save for <strong>{formatDateToDDMMYYYY(selectedDate)}</strong>.
                </span>
              )}
            </div>

            {feedback && (
              <div className={`feedback-alert feedback-${feedback.type}`}>
                <span className="alert-icon">
                  {feedback.type === 'success' ? '' : feedback.type === 'error' ? '️' : 'ℹ️'}
                </span>
                <span className="alert-text">{feedback.message}</span>
              </div>
            )}

            {/* Summary Statistics Cards */}
            <div className="kpi-cards-grid">
              <div className="kpi-card cereals-card">
                <div className="kpi-header">
                  <span className="kpi-icon"></span>
                  <span className="kpi-label">Cereals Target</span>
                </div>
                <div className="kpi-value">{cerealsTotal.toLocaleString()} MT</div>
                <div className="kpi-sub">2 Procurement Centers</div>
              </div>

              <div className="kpi-card pulses-card">
                <div className="kpi-header">
                  <span className="kpi-icon"></span>
                  <span className="kpi-label">Pulses Target</span>
                </div>
                <div className="kpi-value">{pulsesTotal.toLocaleString()} MT</div>
                <div className="kpi-sub">3 Procurement Centers</div>
              </div>

              <div className="kpi-card total-card">
                <div className="kpi-header">
                  <span className="kpi-icon"></span>
                  <span className="kpi-label">Total Day Limit</span>
                </div>
                <div className="kpi-value">{totalLimitTons.toLocaleString()} MT</div>
                <div className="kpi-sub">5 Total Centers</div>
              </div>
            </div>

            {/* Daily Procurement Form & Table */}
            <form onSubmit={handleSubmitPlan} className="planner-form">
              <div className="table-card">
                <div className="table-header-bar">
                  <h2>Procurement Centers & Capacity Limits</h2>
                  <span className="table-count-badge">5 Centers Configured</span>
                </div>

                <div className="table-scroll-container">
                  <table className="procurement-table">
                    <thead>
                      <tr>
                        <th>Center ID</th>
                        <th>Center Name</th>
                        <th>Commodity Category</th>
                        <th className="limit-col-header">Procurement Limit (Tons)</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plans.map((center) => {
                        const isCereals = center.category.toLowerCase() === 'cereals';

                        return (
                          <tr key={center.center_id} className={isCereals ? 'row-cereals' : 'row-pulses'}>
                            <td className="center-id-cell">
                              <span className="id-tag">#{center.center_id}</span>
                            </td>
                            <td className="center-name-cell">
                              <strong>{center.center_name}</strong>
                            </td>
                            <td>
                              <span className={`category-pill ${isCereals ? 'pill-cereals' : 'pill-pulses'}`}>
                                {isCereals ? ' Cereals' : ' Pulses'}
                              </span>
                            </td>
                            <td className="limit-input-cell">
                              <div className="input-with-unit">
                                <input
                                  type="number"
                                  min="0"
                                  step="10"
                                  className="limit-input"
                                  value={center.limit_tons}
                                  onChange={(e) =>
                                    handleLimitChange(center.center_id, parseFloat(e.target.value))
                                  }
                                  required
                                />
                                <span className="unit-label">Tons</span>
                              </div>
                            </td>
                            <td>
                              <button
                                type="button"
                                className="reset-row-btn"
                                onClick={() =>
                                  handleLimitChange(
                                    center.center_id,
                                    DEFAULT_CENTERS.find((d) => d.center_id === center.center_id)?.limit_tons || 100
                                  )
                                }
                                title="Reset to default example"
                              >
                                Reset
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="form-submit-footer">
                  <div className="submit-info-text">
                    * Submitting saves these limits in the database for <strong>{formatDateToDDMMYYYY(selectedDate)}</strong> and carries them forward to future planning dates.
                  </div>
                  <button
                    type="submit"
                    className="submit-plan-btn"
                    disabled={submitting}
                  >
                    {submitting ? ' Submitting Plan...' : ` Submit Day Plan for ${formatDateToDDMMYYYY(selectedDate)}`}
                  </button>
                </div>
              </div>
            </form>
          </main>
        )}

        {/* Page 2: The Live Report */}
        {activeTab === 'live' && (
          <main className="page-container live-page">
            {/* ── Page Header ── */}
            <div className="page-header-section">
              <div>
                <h1 className="page-main-title">The Live Report</h1>
                <p className="page-description">
                  Real-time tokens distributed &amp; crop quantity arriving at each procurement centre.
                  {liveData && (
                    <span className="estimate-note">
                      &nbsp;(Qty estimated at {liveData.tons_per_token_estimate} MT/token)
                    </span>
                  )}
                </p>
              </div>
              <div className="live-header-right">
                <div className="live-indicator">
                  <span className="pulse-dot"></span>
                  <span>Live — Auto refreshes every 30s</span>
                </div>
                <button
                  id="live-refresh-btn"
                  type="button"
                  className={`refresh-btn ${isRefreshing ? 'spinning' : ''}`}
                  onClick={() => fetchLiveReport(true)}
                  disabled={isRefreshing}
                  title="Refresh now"
                >
                  ↻
                </button>
              </div>
            </div>

            {/* ── Last Updated ── */}
            {lastUpdated && (
              <div className="last-updated-bar">
                <span className="last-updated-dot">●</span>
                Last updated: {lastUpdated.toLocaleTimeString()}
              </div>
            )}

            {/* ── Error banner ── */}
            {liveError && (
              <div className="feedback-alert feedback-error">
                <span className="alert-icon">️</span>
                <span className="alert-text">Could not fetch live data: {liveError}</span>
              </div>
            )}

            {/* ── Overview KPI Cards ── */}
            <div className="kpi-cards-grid">
              <div className="kpi-card live-tokens-card">
                <div className="kpi-header">
                  <span className="kpi-icon">️</span>
                  <span className="kpi-label">Tokens Issued Today</span>
                </div>
                <div className="kpi-value">
                  {liveLoading ? <span className="kpi-skeleton"/> : `${liveData?.totals.total_tokens ?? 0} Tokens`}
                </div>
                <div className="kpi-sub">Across 5 Active Centers</div>
              </div>

              <div className="kpi-card live-procured-card">
                <div className="kpi-header">
                  <span className="kpi-icon">️</span>
                  <span className="kpi-label">Estimated Quantity</span>
                </div>
                <div className="kpi-value">
                  {liveLoading
                    ? <span className="kpi-skeleton"/>
                    : `${liveData?.totals.total_filled_tons.toFixed(1) ?? 0} MT`
                  }
                </div>
                <div className="kpi-sub">
                  Out of {liveData?.totals.total_limit_tons.toLocaleString() ?? '—'} MT Limit
                </div>
              </div>

              <div className="kpi-card live-fill-card">
                <div className="kpi-header">
                  <span className="kpi-icon"></span>
                  <span className="kpi-label">Total Limit Filled</span>
                </div>
                <div className="kpi-value">
                  {liveLoading
                    ? <span className="kpi-skeleton"/>
                    : `${liveData?.totals.total_fill_percent ?? 0}%`
                  }
                </div>
                <div className="kpi-sub">Capacity Utilization</div>
              </div>
            </div>

            {/* ── Center-wise Cards Grid ── */}
            <div className="live-reports-container">
              <div className="section-header">
                <h2>Centre-wise Live Token &amp; Procurement Status</h2>
                <span className="badge-live-tag">
                  {liveData ? `Data for ${liveData.date}` : 'Fetching...'}
                </span>
              </div>

              {/* Loading skeletons */}
              {liveLoading && !liveData && (
                <div className="center-live-cards-grid">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <div key={n} className="live-center-card skeleton-card">
                      <div className="sk-line sk-title"/>
                      <div className="sk-line sk-sub"/>
                      <div className="sk-metrics">
                        <div className="sk-box"/>
                        <div className="sk-box"/>
                      </div>
                      <div className="sk-line sk-bar"/>
                    </div>
                  ))}
                </div>
              )}

              {/* Empty state — no data yet */}
              {!liveLoading && liveData && liveData.totals.total_tokens === 0 && (
                <div className="live-empty-state">
                  <span className="empty-icon"></span>
                  <p className="empty-title">No Bookings Yet</p>
                  <p className="empty-sub">
                    No farmer tokens have been issued yet for today.<br/>
                    Once farmers book via the Telegram bot, live data will appear here.
                  </p>
                </div>
              )}

              {/* Real center cards */}
              {liveData && liveData.totals.total_tokens > 0 && (
                <div className="center-live-cards-grid">
                  {liveData.centers.map((center) => {
                    const isCereals = center.category.toLowerCase() === 'cereals';
                    const fillPct = center.fill_percent;
                    const fillColor =
                      fillPct >= 90 ? '#ef4444'
                      : fillPct >= 70 ? '#10b981'
                      : '#3b82f6';
                    const statusLabel =
                      fillPct >= 90 ? 'Near capacity'
                      : fillPct >= 50 ? 'Operating normally'
                      : 'Accepting arrivals';

                    return (
                      <div
                        key={center.center_id}
                        className={`live-center-card ${fillPct >= 90 ? 'card-near-full' : ''}`}
                      >
                        <div className="card-top-bar">
                          <div className="center-identity">
                            <span className="center-code">
                              #{String(center.center_id).padStart(2, '0')}
                            </span>
                            <h3 className="center-title">{center.center_name}</h3>
                          </div>
                          <span className={`category-pill ${isCereals ? 'pill-cereals' : 'pill-pulses'}`}>
                            {isCereals ? ' Cereals' : ' Pulses'}
                          </span>
                        </div>

                        <div className="metrics-split">
                          <div className="metric-box">
                            <span className="metric-lbl">Tokens Distributed</span>
                            <span className="metric-num metric-tokens">
                              ️ {center.tokens_distributed.toLocaleString()}
                            </span>
                            <span className="metric-unit">farmers booked</span>
                          </div>
                          <div className="metric-box">
                            <span className="metric-lbl">Quantity Filled</span>
                            <span className="metric-num">
                              {center.quantity_filled_tons.toFixed(1)}
                              <span className="metric-of"> / {center.limit_tons} MT</span>
                            </span>
                            <span className="metric-unit">estimated arrival</span>
                          </div>
                        </div>

                        {/* Limit Capacity Slider */}
                        <div className="live-progress-bar-wrapper">
                          <div className="progress-label-row">
                            <span>Limit Capacity</span>
                            <strong style={{ color: fillColor }}>
                              {fillPct}%
                            </strong>
                          </div>
                          <div className="bar-bg">
                            <div
                              className="bar-fill"
                              style={{ width: `${Math.min(fillPct, 100)}%`, backgroundColor: fillColor }}
                            />
                          </div>
                          <div className="bar-limits-row">
                            <span>0 MT</span>
                            <span>{center.limit_tons} MT</span>
                          </div>
                        </div>

                        <div className="live-card-footer">
                          <span
                            className="status-dot-green"
                            style={{ color: fillPct >= 90 ? '#f87171' : '#4ade80' }}
                          >
                            ● {statusLabel}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </main>
        )}

        {/* Page 3: Delivery Status */}
        {activeTab === 'status' && (
          <DeliveryStatusPanel />
        )}
      </div>
    </div>
  );
};
