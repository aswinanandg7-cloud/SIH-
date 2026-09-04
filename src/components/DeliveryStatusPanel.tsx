/* eslint-disable */
import React, { useState, useEffect } from 'react';
import './DeliveryStatusPanel.css';
import { Html5QrcodeScanner } from 'html5-qrcode';


const formatDateToDDMMYYYY = (isoDate: string) => {
  if (!isoDate) return '';
  const parts = isoDate.split('-');
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  }
  return isoDate;
};

export const DeliveryStatusPanel: React.FC = () => {

  const [token, setToken] = useState('');
  const [booking, setBooking] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isAutoRefresh, setIsAutoRefresh] = useState(true);
  const [updateLoading, setUpdateLoading] = useState(false);
  const [scannerActive, setScannerActive] = useState(false);

  const fetchBooking = async (searchToken: string) => {
    if (!searchToken) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`/api/booking/${searchToken}`);
      if (!res.ok) {
        throw new Error('Booking not found');
      }
      const data = await res.json();
      setBooking(data);
    } catch (err: any) {
      setBooking(null);
      setError(err.message || 'Error fetching booking');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchBooking(token);
  };

  // Auto-refresh every 5 seconds
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isAutoRefresh && booking && token) {
      interval = setInterval(() => {
        fetchBooking(token);
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [isAutoRefresh, booking, token]);

  useEffect(() => {
    if (scannerActive) {
      const scanner = new Html5QrcodeScanner(
        "qr-reader",
        { fps: 10, qrbox: { width: 250, height: 250 } },
        false
      );

      scanner.render((decodedText) => {
        // Extract token
        let extractedToken = decodedText;
        if (decodedText.includes(':')) {
            extractedToken = decodedText.split(':')[1];
        }
        setToken(extractedToken);
        setScannerActive(false);
        scanner.clear();
        fetchBooking(extractedToken);
      }, () => {
        // Handle scan error optionally
      });

      return () => {
        scanner.clear().catch(error => {
          console.error("Failed to clear html5QrcodeScanner. ", error);
        });
      };
    }
  }, [scannerActive]);

  const updateStatus = async (newStatus: string) => {
    if (!booking) return;
    setUpdateLoading(true);
    try {
      const res = await fetch(`/api/booking/${booking.token}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) throw new Error('Failed to update status');
      fetchBooking(booking.token);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setUpdateLoading(false);
    }
  };

  const statuses = ["BOOKED", "ARRIVED", "WEIGHED", "GRADED", "COLLECTED", "PAID"];
  const currentStatusIndex = booking ? statuses.indexOf(booking.status) : -1;

  return (
    <main className="page-container delivery-page">
      <div className="page-header-section">
        <div>
          <h1 className="page-main-title">Delivery Status & Verification</h1>
          <p className="page-description">
            Search tokens via number or QR.
          </p>
        </div>
      </div>

      <div className="search-section card">
        {scannerActive ? (
          <div className="scanner-container">
            <div id="qr-reader" style={{ width: '100%', maxWidth: '500px', margin: '0 auto' }}></div>
            <button type="button" className="btn-secondary mt-4" onClick={() => setScannerActive(false)}>
              Cancel Scanning
            </button>
          </div>
        ) : (
          <form onSubmit={handleSearch} className="search-form">
            <input
              type="text"
              placeholder="Enter Token Number..."
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="token-input"
            />
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Searching...' : 'Search'}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setScannerActive(true)}>
              Scan QR
            </button>
          </form>
        )}
        {error && <p className="error-text">{error}</p>}
      </div>

      {booking && (
        <div className="booking-details card mt-4">
          <div className="card-header flex-between">
            <h2>Booking Info: {booking.token}</h2>
            <div className="refresh-toggle">
              <label>
                <input 
                  type="checkbox" 
                  checked={isAutoRefresh} 
                  onChange={(e) => setIsAutoRefresh(e.target.checked)} 
                /> Live Updates (5s)
              </label>
            </div>
          </div>
          <div className="details-grid">
            <div><strong>Farmer Name:</strong> {booking.farmer_name}</div>
            <div><strong>Crop:</strong> {booking.crop}</div>
            <div><strong>Center:</strong> {booking.center_name}</div>
            <div><strong>Quantity:</strong> {booking.quantity_tons} Tons</div>
            <div><strong>Time Slot:</strong> {booking.time_slot}</div>
            <div><strong>Date:</strong> {formatDateToDDMMYYYY(booking.booking_date)}</div>
          </div>

          <div className="status-timeline mt-6">
            <h3>Current Status: <span className="status-badge">{booking.status}</span></h3>
            <div className="steps-container mt-4">
              {statuses.map((status, index) => (
                <div key={status} className={`step ${index <= currentStatusIndex ? 'completed' : ''}`}>
                  <div className="step-circle">{index + 1}</div>
                  <div className="step-label">{status}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="action-buttons mt-6">
            <h3>Update Status</h3>
            <div className="button-group">
              {statuses.filter(s => s !== 'BOOKED').map((status) => {
                const originalIndex = statuses.indexOf(status);
                return (
                  <button
                    key={status}
                    className={`btn-action ${booking.status === status ? 'active' : ''}`}
                    onClick={() => updateStatus(status)}
                    disabled={updateLoading || originalIndex < currentStatusIndex || originalIndex > currentStatusIndex + 1}
                  >
                    Mark as {status}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </main>
  );
};
