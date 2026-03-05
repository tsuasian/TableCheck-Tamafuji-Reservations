import { useState, useCallback, useEffect } from 'react';
import type { Watch } from './types';
import { listWatches, ApiClientError } from './api';
import WatchForm from './components/WatchForm';
import WatchList from './components/WatchList';

function normalizePhone(raw: string): string {
  const digits = raw.replace(/[\s()\-]/g, '');
  if (digits.startsWith('+')) return digits;
  if (digits.length === 10) return `+1${digits}`;
  if (digits.length === 11 && digits.startsWith('1')) return `+${digits}`;
  return digits;
}

type Tab = 'new' | 'watches';

interface Toast {
  id: number;
  message: string;
  isError: boolean;
  exiting: boolean;
}

let toastId = 0;

export default function App() {
  const [tab, setTab] = useState<Tab>('new');
  const [phone, setPhone] = useState('');
  const [lookupPhone, setLookupPhone] = useState('');
  const [watches, setWatches] = useState<Watch[]>([]);
  const [loading, setLoading] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, isError = false) => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, message, isError, exiting: false }]);
    setTimeout(() => {
      setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t));
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 250);
    }, 3000);
  }, []);

  const fetchWatches = useCallback(async (p: string) => {
    if (!p) return;
    setLoading(true);
    try {
      const data = await listWatches(p);
      setWatches(data);
    } catch (err) {
      if (err instanceof ApiClientError) {
        showToast(err.message, true);
      }
      setWatches([]);
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    const clean = normalizePhone(phone);
    setLookupPhone(clean);
    setTab('watches');
    fetchWatches(clean);
  }

  function handleCreated(createdPhone: string) {
    setPhone(createdPhone);
    setLookupPhone(createdPhone);
    setTab('watches');
    fetchWatches(createdPhone);
  }

  useEffect(() => {
    if (tab === 'watches' && lookupPhone) {
      fetchWatches(lookupPhone);
    }
  }, [tab, lookupPhone, fetchWatches]);

  return (
    <div className="app">
      {/* Toast notifications */}
      {toasts.length > 0 && (
        <div className="toast-container">
          {toasts.map(t => (
            <div key={t.id} className={`toast ${t.isError ? 'error' : ''} ${t.exiting ? 'toast-exit' : ''}`}>
              {t.message}
            </div>
          ))}
        </div>
      )}

      {/* Header */}
      <header className="header">
        <div className="header-ornament">&#x2022; &#x2022; &#x2022;</div>
        <h1>Tamafuji</h1>
        <p className="header-subtitle">Reservation Watcher</p>
      </header>

      {/* Phone Lookup */}
      <form className="lookup" onSubmit={handleLookup}>
        <div className="lookup-row">
          <input
            type="tel"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            placeholder="Enter phone to view watches"
          />
          <button type="submit" className="btn btn-secondary">
            Look up
          </button>
        </div>
      </form>

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${tab === 'new' ? 'active' : ''}`}
          onClick={() => setTab('new')}
          type="button"
        >
          New Watch
        </button>
        <button
          className={`tab ${tab === 'watches' ? 'active' : ''}`}
          onClick={() => setTab('watches')}
          type="button"
        >
          Your Watches{watches.length > 0 ? ` (${watches.length})` : ''}
        </button>
      </div>

      {/* Content */}
      {tab === 'new' && (
        <WatchForm onCreated={handleCreated} showToast={showToast} />
      )}
      {tab === 'watches' && (
        <WatchList
          watches={watches}
          loading={loading}
          onRefresh={() => fetchWatches(lookupPhone)}
          showToast={showToast}
        />
      )}
    </div>
  );
}
