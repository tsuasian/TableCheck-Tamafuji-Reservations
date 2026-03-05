import { useState } from 'react';
import type { Watch } from '../types';
import { updateWatch, deleteWatch, ApiClientError } from '../api';

interface WatchListProps {
  watches: Watch[];
  loading: boolean;
  onRefresh: () => void;
  showToast: (msg: string, isError?: boolean) => void;
}

function to12h(time24: string): string {
  const [h, m] = time24.split(':').map(Number);
  const period = h >= 12 ? 'PM' : 'AM';
  const hour = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${hour}:${m.toString().padStart(2, '0')} ${period}`;
}

function formatDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export default function WatchList({ watches, loading, onRefresh, showToast }: WatchListProps) {
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="loading-bar">
        <div className="loading-bar-inner" />
      </div>
    );
  }

  if (watches.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">&#x2615;</div>
        <p>No watches yet. Create one to get notified when a table opens up.</p>
      </div>
    );
  }

  async function handleToggle(watch: Watch) {
    setActionLoading(watch.watch_id);
    try {
      await updateWatch(watch.watch_id, {
        phone: watch.phone,
        is_active: !watch.is_active,
      });
      onRefresh();
    } catch (err) {
      showToast(err instanceof ApiClientError ? err.message : 'Failed to update', true);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDelete(watch: Watch) {
    setActionLoading(watch.watch_id);
    setConfirmId(null);
    try {
      await deleteWatch(watch.watch_id, watch.phone);
      showToast('Watch deleted');
      onRefresh();
    } catch (err) {
      showToast(err instanceof ApiClientError ? err.message : 'Failed to delete', true);
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <>
      {watches.map(watch => (
        <div
          key={watch.watch_id}
          className={`watch-card ${!watch.is_active ? 'inactive' : ''}`}
          style={actionLoading === watch.watch_id ? { opacity: 0.5, pointerEvents: 'none' } : {}}
        >
          <div className="watch-card-header">
            <span className="watch-card-id">#{watch.watch_id}</span>
            <div className="watch-card-actions">
              <button
                className={`toggle ${watch.is_active ? 'active' : ''}`}
                onClick={() => handleToggle(watch)}
                title={watch.is_active ? 'Pause watch' : 'Resume watch'}
                type="button"
              />
              <button
                className="btn btn-danger"
                onClick={() => setConfirmId(watch.watch_id)}
                type="button"
              >
                Delete
              </button>
            </div>
          </div>
          <div className="watch-card-body">
            <div className="watch-card-row">
              <span className="watch-card-label">Dates</span>
              <span className="watch-card-value">
                {watch.dates.map(d => (
                  <span key={d} className="watch-date-tag">{formatDate(d)}</span>
                ))}
              </span>
            </div>
            <div className="watch-card-row">
              <span className="watch-card-label">Party</span>
              <span className="watch-card-value">{watch.party_size}</span>
            </div>
            <div className="watch-card-row">
              <span className="watch-card-label">Times</span>
              <span className="watch-card-value">
                {watch.preferred_times ? (
                  watch.preferred_times.map(t => (
                    <span key={t} className="watch-time-tag">{to12h(t)}</span>
                  ))
                ) : (
                  <span className="watch-time-tag">Any time</span>
                )}
              </span>
            </div>
          </div>

          {confirmId === watch.watch_id && (
            <div className="confirm-overlay" onClick={() => setConfirmId(null)}>
              <div className="confirm-dialog" onClick={e => e.stopPropagation()}>
                <p>Delete this watch? This can't be undone.</p>
                <div className="confirm-actions">
                  <button className="btn btn-ghost" onClick={() => setConfirmId(null)} type="button">
                    Cancel
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={() => handleDelete(watch)}
                    type="button"
                    style={{ background: '#7f1d1d', color: 'white', borderRadius: '6px' }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ))}
    </>
  );
}
