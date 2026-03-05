import { useMemo, useState } from 'react';

interface DatePickerProps {
  selected: string[];
  onChange: (dates: string[]) => void;
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function toISO(d: Date): string {
  return d.toISOString().split('T')[0];
}

function isTuesday(d: Date): boolean {
  return d.getDay() === 2;
}

export default function DatePicker({ selected, onChange }: DatePickerProps) {
  const today = useMemo(() => new Date(), []);
  const todayStr = toISO(today);

  // Informational only — checker won't poll until date is within window
  const windowMin = useMemo(() => {
    const d = new Date(today);
    d.setDate(d.getDate() + 7);
    return d;
  }, [today]);

  // Available months: current month + next 3
  const availableMonths = useMemo(() => {
    const months: Date[] = [];
    for (let i = 0; i < 4; i++) {
      months.push(new Date(today.getFullYear(), today.getMonth() + i, 1));
    }
    return months;
  }, [today]);

  const [monthIndex, setMonthIndex] = useState(0);

  function toggleDate(dateStr: string) {
    if (selected.includes(dateStr)) {
      onChange(selected.filter(d => d !== dateStr));
    } else {
      onChange([...selected, dateStr].sort());
    }
  }

  function renderMonth(monthStart: Date) {
    const year = monthStart.getFullYear();
    const month = monthStart.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    const firstDayJS = new Date(year, month, 1).getDay();
    const startOffset = firstDayJS === 0 ? 6 : firstDayJS - 1;

    const cells: React.ReactNode[] = [];

    for (let i = 0; i < startOffset; i++) {
      cells.push(<div key={`empty-${i}`} className="calendar-day empty" />);
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const d = new Date(year, month, day);
      const dateStr = toISO(d);
      const isToday = dateStr === todayStr;
      const closed = isTuesday(d);
      const past = d < today;
      const tooSoon = d >= today && d < windowMin;
      const disabled = closed || past;
      const isSelected = selected.includes(dateStr);

      let label = '';
      if (closed) label = 'Closed';
      else if (tooSoon) label = 'Too soon';

      const classes = [
        'calendar-day',
        isToday && 'today',
        isSelected && 'selected',
        closed && 'closed',
        past && !closed && 'disabled',
        tooSoon && !isSelected && 'too-soon',
      ].filter(Boolean).join(' ');

      cells.push(
        <button
          key={dateStr}
          className={classes}
          disabled={disabled}
          onClick={() => toggleDate(dateStr)}
          title={label || undefined}
          type="button"
        >
          <span>{day}</span>
          {label && <span className="calendar-day-label">{label}</span>}
        </button>
      );
    }

    return (
      <>
        <div className="calendar-weekdays">
          {WEEKDAY_LABELS.map(w => (
            <div key={w} className="calendar-weekday">{w}</div>
          ))}
        </div>
        <div className="calendar-days">{cells}</div>
      </>
    );
  }

  const currentMonth = availableMonths[monthIndex];

  return (
    <div className="calendar-container">
      <div className="calendar-month">
        <div className="calendar-nav">
          <button
            type="button"
            className="calendar-nav-btn"
            disabled={monthIndex === 0}
            onClick={() => setMonthIndex(i => i - 1)}
            aria-label="Previous month"
          >
            &#8249;
          </button>
          <select
            className="calendar-month-select"
            value={monthIndex}
            onChange={e => setMonthIndex(Number(e.target.value))}
          >
            {availableMonths.map((m, i) => (
              <option key={i} value={i}>
                {MONTH_NAMES[m.getMonth()]} {m.getFullYear()}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="calendar-nav-btn"
            disabled={monthIndex === availableMonths.length - 1}
            onClick={() => setMonthIndex(i => i + 1)}
            aria-label="Next month"
          >
            &#8250;
          </button>
        </div>
        {renderMonth(currentMonth)}
      </div>
    </div>
  );
}
