interface TimeSlotPickerProps {
  selectedDates: string[];
  selectedTimes: string[] | null;
  onChange: (times: string[] | null) => void;
}

const WEEKDAY_SLOTS = ['16:00', '17:30', '19:00', '20:30'];
const WEEKEND_SLOTS = ['11:00', '12:30', '17:00', '18:30', '20:00'];

function to12h(time24: string): string {
  const [h, m] = time24.split(':').map(Number);
  const period = h >= 12 ? 'PM' : 'AM';
  const hour = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${hour}:${m.toString().padStart(2, '0')} ${period}`;
}

function isWeekend(dateStr: string): boolean {
  const d = new Date(dateStr + 'T00:00:00');
  const day = d.getDay();
  return day === 0 || day === 6;
}

export default function TimeSlotPicker({
  selectedDates,
  selectedTimes,
  onChange,
}: TimeSlotPickerProps) {
  const hasWeekday = selectedDates.some(d => !isWeekend(d));
  const hasWeekend = selectedDates.some(d => isWeekend(d));

  const slots = new Set<string>();
  if (hasWeekday) WEEKDAY_SLOTS.forEach(s => slots.add(s));
  if (hasWeekend) WEEKEND_SLOTS.forEach(s => slots.add(s));

  const sortedSlots = Array.from(slots).sort();
  const isAnyTime = selectedTimes === null;

  if (selectedDates.length === 0) {
    return (
      <p className="field-hint">Select dates first to see available time slots</p>
    );
  }

  function toggleSlot(slot: string) {
    if (isAnyTime) {
      onChange([slot]);
      return;
    }
    if (selectedTimes!.includes(slot)) {
      const next = selectedTimes!.filter(t => t !== slot);
      onChange(next.length === 0 ? null : next);
    } else {
      onChange([...selectedTimes!, slot].sort());
    }
  }

  return (
    <div className="time-chips">
      <button
        type="button"
        className={`time-chip any-time ${isAnyTime ? 'selected' : ''}`}
        onClick={() => onChange(null)}
      >
        Any time
      </button>
      {sortedSlots.map(slot => (
        <button
          key={slot}
          type="button"
          className={`time-chip ${!isAnyTime && selectedTimes!.includes(slot) ? 'selected' : ''}`}
          onClick={() => toggleSlot(slot)}
        >
          {to12h(slot)}
        </button>
      ))}
    </div>
  );
}
