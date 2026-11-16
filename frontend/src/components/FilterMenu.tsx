import {useEffect, useId, useRef, useState} from 'react';

export interface FilterOption {
  key: string;
  label: string;
  checked: boolean;
  onToggle: () => void;
}

// A filter dropdown: a button that shows how many options are on, opening a
// panel of checkboxes. Escape, a click outside, or keyboard focus leaving the
// menu closes it; Escape returns focus to the button. The checkboxes are
// ordinary inputs, so Tab and Space work inside the panel. `align="right"`
// opens the panel leftwards from the button's right edge (for the last menu
// in a row, so it stays on screen at phone width).
export function FilterMenu({
  label,
  options,
  align = 'left',
}: {
  label: string;
  options: FilterOption[];
  align?: 'left' | 'right';
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const on = options.filter((o) => o.checked).length;

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (e: MouseEvent) => {
      if (root.current && e.target instanceof Node && !root.current.contains(e.target)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div
      className="filter-menu"
      ref={root}
      onBlur={(e) => {
        // Tabbing out of the menu (not between its own controls) closes it.
        if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false);
      }}
    >
      <button
        ref={button}
        type="button"
        className={on > 0 ? 'filter-button active' : 'filter-button'}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
      >
        {label}
        {on > 0 && <span className="filter-count"> {on}</span>}
        <span aria-hidden="true"> ▾</span>
      </button>
      {open && (
        <fieldset
          id={panelId}
          className={align === 'right' ? 'filter-panel align-right' : 'filter-panel'}
        >
          <legend className="visually-hidden">{label}</legend>
          {options.map((o) => (
            <label key={o.key} className="inline">
              <input type="checkbox" checked={o.checked} onChange={o.onToggle} />
              {o.label}
            </label>
          ))}
        </fieldset>
      )}
    </div>
  );
}
