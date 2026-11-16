import {cleanup} from '@testing-library/react';
import {afterEach} from 'vitest';

afterEach(() => cleanup());

// jsdom has no scrollIntoView (every real browser does); components call it
// on open, so give it a no-op stand-in. Tests that check the call stub it.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => undefined;
}
