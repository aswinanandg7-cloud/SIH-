import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import type { SlotItem } from '../types/auth';
import './TokenSlotVisibility.css';

export const TokenSlotVisibility: React.FC = () => {
  const { user, logout } = useAuth();
  const [slots, setSlots] = useState<SlotItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<string>('');

  const fetchSlots = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Fetch from Vite proxy /api/slots (which proxies to http://localhost:8000/slots)
      const res = await fetch('/api/slots');
      
      if (!res.ok) {
        throw new Error(`Backend server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      setSlots(data.slots || []);
      setLastFetched(new Date().toLocaleTimeString());
    } catch (err: any) {
      console.warn('Backend GET /slots fetch warning:', err);
      setError(`Unable to connect to Python backend at http://localhost:8000. Ensure FastAPI is running via 'uvicorn main:app --reload --port 8000'.`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSlots();
  }, [fetchSlots]);

  const totalCapacity = slots.reduce((acc, s) => acc + s.max_capacity, 0);
  const totalRemaining = slots.reduce((acc, s) => acc + s.remaining, 0);

  return (
    <div className="clerk-wrapper">
      <header className="clerk-header">
        <div className="header-brand">
          <div className="portal-icon">🎟️</div>
          <div>
            <h1 className="header-title">Token Slot Visibility</h1>
            <span className="clerk-badge">Role Verified: govt-agri-clerk</span>
          </div>
        </div>

        <div className="user-profile-bar">
          <div className="user-info">
            <span className="user-name">{user?.name || user?.username}</span>
            <span className="user-role-pill">Govt Agri Clerk</span>
          </div>
          <button type="button" className="logout-btn" onClick={logout} title="Sign Out">
            🚪 Logout
          </button>
        </div>
      </header>

      <main className="clerk-container">
        {/* Connection / Refresh Header */}
        <div className="clerk-action-bar">
          <div className="refresh-status">
            <span className="status-dot"></span>
            <span>API Source: <code>GET /slots</code> (FastAPI)</span>
            {lastFetched && <span className="fetch-time">Updated: {lastFetched}</span>}
          </div>

          <button
            type="button"
            className="refresh-btn"
            onClick={fetchSlots}
            disabled={isLoading}
          >
            {isLoading ? '⌛ Refreshing...' : '🔄 Refresh Slots'}
          </button>
        </div>

        {error && (
          <div className="api-error-banner">
            <div className="error-icon">⚡</div>
            <div className="error-body">
              <strong>Backend Connection Note</strong>
              <p>{error}</p>
            </div>
            <button type="button" className="retry-btn" onClick={fetchSlots}>
              Retry API
            </button>
          </div>
        )}

        {/* KPI Stat Cards */}
        <div className="clerk-stats-grid">
          <div className="clerk-stat-card">
            <span className="stat-label">Total Time Slots</span>
            <span className="stat-value">{slots.length} Slots</span>
          </div>
          <div className="clerk-stat-card">
            <span className="stat-label">Total Max Capacity</span>
            <span className="stat-value">{totalCapacity} Tokens</span>
          </div>
          <div className="clerk-stat-card highlight">
            <span className="stat-label">Available Remaining</span>
            <span className="stat-value">{totalRemaining} Tokens</span>
          </div>
        </div>

        {/* Slot Grid */}
        {isLoading && slots.length === 0 ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Fetching token slots from backend...</p>
          </div>
        ) : (
          <div className="slots-grid">
            {slots.map((slot) => {
              const remainingPct = Math.round((slot.remaining / slot.max_capacity) * 100);
              const isFull = slot.remaining === 0;

              return (
                <div key={slot.id} className={`slot-card ${isFull ? 'full' : ''}`}>
                  <div className="slot-header">
                    <span className="slot-id">SLOT #{slot.id}</span>
                    <span className={`slot-status-pill ${isFull ? 'pill-full' : remainingPct < 30 ? 'pill-low' : 'pill-ok'}`}>
                      {isFull ? 'FULL' : `${slot.remaining} Left`}
                    </span>
                  </div>

                  <div className="slot-body">
                    <h3 className="center-name">{slot.center}</h3>
                    <div className="crop-tag">🌾 {slot.crop}</div>
                    <div className="time-range">⏰ {slot.time}</div>
                  </div>

                  <div className="slot-capacity-bar">
                    <div className="capacity-labels">
                      <span>Capacity: {slot.remaining} / {slot.max_capacity}</span>
                      <span>{remainingPct}% Available</span>
                    </div>
                    <div className="bar-bg">
                      <div
                        className="bar-fill"
                        style={{
                          width: `${remainingPct}%`,
                          backgroundColor: remainingPct < 30 ? '#ef4444' : '#10b981',
                        }}
                      ></div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
};
