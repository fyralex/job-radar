import {useId} from 'react';
import {useDisclosure} from '../hooks/useDisclosure';

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
// in a row). It only applies above 640px: on phones every panel is anchored
// to the filter row's left edge instead (see index.css).
export function FilterMenu({
  label,
  options,
  align = 'left',
}: {
  label: string;
  options: FilterOption[];
  align?: 'left' | 'right';
}) {
  const {open, setOpen, root, button, onBlur} = useDisclosure();
  const panelId = useId();
  const on = options.filter((o) => o.checked).length;

  return (
    <div className="filter-menu" ref={root} onBlur={onBlur}>
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
