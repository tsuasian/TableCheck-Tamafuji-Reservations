import { useState } from 'react';
import DatePicker from './DatePicker';
import TimeSlotPicker from './TimeSlotPicker';
import { createWatch, ApiClientError } from '../api';

interface WatchFormProps {
  onCreated: (phone: string) => void;
  showToast: (msg: string, isError?: boolean) => void;
}

function normalizePhone(raw: string): string {
  const digits = raw.replace(/[\s()\-]/g, '');
  if (digits.startsWith('+')) return digits;
  if (digits.length === 10) return `+1${digits}`;
  if (digits.length === 11 && digits.startsWith('1')) return `+${digits}`;
  return digits;
}

export default function WatchForm({ onCreated, showToast }: WatchFormProps) {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [dates, setDates] = useState<string[]>([]);
  const [partySize, setPartySize] = useState(2);
  const [preferredTimes, setPreferredTimes] = useState<string[] | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  function validate(): Record<string, string> {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = 'Name is required';
    const cleanPhone = normalizePhone(phone);
    if (!cleanPhone || !/^\+\d{10,15}$/.test(cleanPhone))
      errs.phone = 'Phone must be E.164 format (e.g. +18081234567)';
    if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
      errs.email = 'Valid email is required';
    if (dates.length === 0) errs.dates = 'Select at least one date';
    return errs;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    const cleanPhone = normalizePhone(phone);
    try {
      await createWatch({
        name: name.trim(),
        email: email.trim(),
        phone: cleanPhone,
        dates,
        party_size: partySize,
        preferred_times: preferredTimes,
      });
      showToast('Watch created successfully');
      onCreated(cleanPhone);
      setName('');
      setPhone('');
      setEmail('');
      setDates([]);
      setPartySize(2);
      setPreferredTimes(null);
      setErrors({});
    } catch (err) {
      if (err instanceof ApiClientError) {
        showToast(err.message, true);
      } else {
        showToast('Something went wrong', true);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label className="field-label">Name</label>
        <input
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Your name"
        />
        {errors.name && <div className="field-error">{errors.name}</div>}
      </div>

      <div className="field">
        <label className="field-label">Phone</label>
        <input
          type="tel"
          value={phone}
          onChange={e => setPhone(e.target.value)}
          placeholder="+1 (808) 123-4567"
        />
        <div className="field-hint">E.164 format with country code</div>
        {errors.phone && <div className="field-error">{errors.phone}</div>}
      </div>

      <div className="field">
        <label className="field-label">Email</label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="you@example.com"
        />
        {errors.email && <div className="field-error">{errors.email}</div>}
      </div>

      <hr className="divider" />

      <div className="field">
        <label className="field-label">Dates</label>
        <DatePicker selected={dates} onChange={setDates} />
        {errors.dates && <div className="field-error">{errors.dates}</div>}
      </div>

      <div className="field">
        <label className="field-label">Party Size</label>
        <div className="party-selector">
          {Array.from({ length: 10 }, (_, i) => i + 1).map(n => (
            <button
              key={n}
              type="button"
              className={`party-btn ${partySize === n ? 'selected' : ''}`}
              onClick={() => setPartySize(n)}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label className="field-label">Preferred Times</label>
        <TimeSlotPicker
          selectedDates={dates}
          selectedTimes={preferredTimes}
          onChange={setPreferredTimes}
        />
      </div>

      <hr className="divider" />

      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? 'Creating...' : 'Create Watch'}
      </button>
    </form>
  );
}
