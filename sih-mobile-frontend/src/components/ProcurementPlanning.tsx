import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import type { ProcurementPlanItem } from '../types/auth';
import './ProcurementPlanning.css';

const INITIAL_PLANS: ProcurementPlanItem[] = [
  {
    id: 'PRC-2026-001',
    district: 'Ludhiana, Punjab',
    cropType: 'Wheat',
    targetQuantityTons: 45000,
    procuredQuantityTons: 38200,
    status: 'Active',
    mspPerQuintal: 2275,
    allocatedBudgetLakhs: 1023.75,
    startDate: '2026-03-15',
    endDate: '2026-05-30',
  },
  {
    id: 'PRC-2026-002',
    district: 'Karnal, Haryana',
    cropType: 'Wheat',
    targetQuantityTons: 32000,
    procuredQuantityTons: 29800,
    status: 'Active',
    mspPerQuintal: 2275,
    allocatedBudgetLakhs: 728.0,
    startDate: '2026-03-20',
    endDate: '2026-05-25',
  },
  {
    id: 'PRC-2026-003',
    district: 'Bardhaman, West Bengal',
    cropType: 'Paddy (Rice)',
    targetQuantityTons: 50000,
    procuredQuantityTons: 50000,
    status: 'Completed',
    mspPerQuintal: 2183,
    allocatedBudgetLakhs: 1091.5,
    startDate: '2026-01-10',
    endDate: '2026-04-15',
  },
  {
    id: 'PRC-2026-004',
    district: 'Guntur, Andhra Pradesh',
    cropType: 'Pulses',
    targetQuantityTons: 18000,
    procuredQuantityTons: 6400,
    status: 'Planning',
    mspPerQuintal: 6600,
    allocatedBudgetLakhs: 1188.0,
    startDate: '2026-09-01',
    endDate: '2026-11-30',
  },
];

export const ProcurementPlanning: React.FC = () => {
  const { user, logout } = useAuth();
  const [plans, setPlans] = useState<ProcurementPlanItem[]>(INITIAL_PLANS);
  const [selectedCrop, setSelectedCrop] = useState<string>('All');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [showAddModal, setShowAddModal] = useState<boolean>(false);

  // New item form state
  const [newDistrict, setNewDistrict] = useState<string>('');
  const [newCrop, setNewCrop] = useState<'Wheat' | 'Paddy (Rice)' | 'Pulses' | 'Maize' | 'Mustard'>('Wheat');
  const [newTarget, setNewTarget] = useState<number>(10000);
  const [newMsp, setNewMsp] = useState<number>(2400);

  const filteredPlans = plans.filter((plan) => {
    const matchesCrop = selectedCrop === 'All' || plan.cropType === selectedCrop;
    const matchesSearch =
      plan.district.toLowerCase().includes(searchTerm.toLowerCase()) ||
      plan.id.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCrop && matchesSearch;
  });

  const totalTargetTons = plans.reduce((acc, p) => acc + p.targetQuantityTons, 0);
  const totalProcuredTons = plans.reduce((acc, p) => acc + p.procuredQuantityTons, 0);
  const totalBudgetLakhs = plans.reduce((acc, p) => acc + p.allocatedBudgetLakhs, 0);

  const handleAddPlan = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDistrict.trim()) return;

    const newId = `PRC-2026-${String(plans.length + 1).padStart(3, '0')}`;
    const budget = (newTarget * 10 * newMsp) / 100000;

    const newItem: ProcurementPlanItem = {
      id: newId,
      district: newDistrict,
      cropType: newCrop,
      targetQuantityTons: newTarget,
      procuredQuantityTons: 0,
      status: 'Planning',
      mspPerQuintal: newMsp,
      allocatedBudgetLakhs: parseFloat(budget.toFixed(2)),
      startDate: '2026-09-01',
      endDate: '2026-12-31',
    };

    setPlans([newItem, ...plans]);
    setShowAddModal(false);
    setNewDistrict('');
  };

  return (
    <div className="procurement-wrapper">
      <header className="procurement-header">
        <div className="header-brand">
          <div className="portal-icon">🌾</div>
          <div>
            <h1 className="header-title">Procurement Planning Portal</h1>
            <span className="gov-badge">Role Verified: govt-agri-officer</span>
          </div>
        </div>

        <div className="user-profile-bar">
          <div className="user-info">
            <span className="user-name">{user?.name || user?.username}</span>
            <span className="user-role-pill">Govt Agri Officer</span>
          </div>
          <button type="button" className="logout-btn" onClick={logout} title="Sign Out">
            🚪 Logout
          </button>
        </div>
      </header>

      <main className="procurement-container">
        {/* KPI Stat Cards */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon target">🎯</div>
            <div className="stat-content">
              <span className="stat-label">Total Target</span>
              <span className="stat-value">{totalTargetTons.toLocaleString()} MT</span>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon procured">🚜</div>
            <div className="stat-content">
              <span className="stat-label">Procured to Date</span>
              <span className="stat-value">{totalProcuredTons.toLocaleString()} MT</span>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon budget">💰</div>
            <div className="stat-content">
              <span className="stat-label">Budget Allocation</span>
              <span className="stat-value">₹{totalBudgetLakhs.toLocaleString()} L</span>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon active">📍</div>
            <div className="stat-content">
              <span className="stat-label">Active Centers</span>
              <span className="stat-value">{plans.length} Districts</span>
            </div>
          </div>
        </div>

        {/* Toolbar & Controls */}
        <div className="toolbar">
          <div className="search-box">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search district or plan ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="filter-box">
            <label>Crop:</label>
            <select value={selectedCrop} onChange={(e) => setSelectedCrop(e.target.value)}>
              <option value="All">All Crops</option>
              <option value="Wheat">Wheat</option>
              <option value="Paddy (Rice)">Paddy (Rice)</option>
              <option value="Pulses">Pulses</option>
            </select>
          </div>

          <button type="button" className="add-plan-btn" onClick={() => setShowAddModal(true)}>
            ➕ Create Plan
          </button>
        </div>

        {/* Procurement Plans Table / Cards */}
        <div className="plan-list">
          {filteredPlans.length === 0 ? (
            <div className="no-data">No procurement plans matching search criteria.</div>
          ) : (
            filteredPlans.map((plan) => {
              const progressPct = Math.min(
                100,
                Math.round((plan.procuredQuantityTons / plan.targetQuantityTons) * 100)
              );

              return (
                <div key={plan.id} className="plan-card">
                  <div className="plan-header">
                    <div>
                      <span className="plan-id">{plan.id}</span>
                      <h3 className="plan-district">{plan.district}</h3>
                    </div>
                    <span className={`status-badge status-${plan.status.toLowerCase().replace(' ', '-')}`}>
                      {plan.status}
                    </span>
                  </div>

                  <div className="plan-details-grid">
                    <div className="detail-item">
                      <span className="detail-label">Crop Type</span>
                      <span className="detail-val">{plan.cropType}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">MSP (₹/Quintal)</span>
                      <span className="detail-val">₹{plan.mspPerQuintal}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Target / Procured</span>
                      <span className="detail-val">
                        {plan.procuredQuantityTons.toLocaleString()} / {plan.targetQuantityTons.toLocaleString()} MT
                      </span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Allocated Budget</span>
                      <span className="detail-val">₹{plan.allocatedBudgetLakhs} Lakhs</span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="progress-section">
                    <div className="progress-bar-bg">
                      <div className="progress-fill" style={{ width: `${progressPct}%` }}></div>
                    </div>
                    <span className="progress-text">{progressPct}% Procured</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </main>

      {/* Add Plan Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Create New Procurement Plan</h2>
            <form onSubmit={handleAddPlan}>
              <div className="modal-form-group">
                <label>District & State</label>
                <input
                  type="text"
                  placeholder="e.g. Ludhiana, Punjab"
                  value={newDistrict}
                  onChange={(e) => setNewDistrict(e.target.value)}
                  required
                />
              </div>

              <div className="modal-form-group">
                <label>Crop Type</label>
                <select
                  value={newCrop}
                  onChange={(e) => setNewCrop(e.target.value as any)}
                >
                  <option value="Wheat">Wheat</option>
                  <option value="Paddy (Rice)">Paddy (Rice)</option>
                  <option value="Pulses">Pulses</option>
                  <option value="Maize">Maize</option>
                  <option value="Mustard">Mustard</option>
                </select>
              </div>

              <div className="modal-form-group">
                <label>Target Quantity (Metric Tons)</label>
                <input
                  type="number"
                  value={newTarget}
                  onChange={(e) => setNewTarget(Number(e.target.value))}
                  required
                />
              </div>

              <div className="modal-form-group">
                <label>MSP Rate (₹/Quintal)</label>
                <input
                  type="number"
                  value={newMsp}
                  onChange={(e) => setNewMsp(Number(e.target.value))}
                  required
                />
              </div>

              <div className="modal-actions">
                <button type="button" className="cancel-btn" onClick={() => setShowAddModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="submit-btn">
                  Create Allocation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
