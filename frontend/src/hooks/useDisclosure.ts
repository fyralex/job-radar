import {type FocusEvent, useEffect, useRef, useState} from 'react';

// Open/close state for a button that shows a small panel (the filter and
// action menus). Escape closes it and puts focus back on the button; a mouse
// press outside `root` closes it; keyboard focus leaving `root` closes it. A
// blur with no new focus target (a click on empty panel space, switching
// windows) is left alone, since outside presses are handled separately.
export function useDisclosure() {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

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

  const onBlur = (e: FocusEvent<HTMLDivElement>) => {
    if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) setOpen(false);
  };

  return {open, setOpen, root, button, onBlur};
}
