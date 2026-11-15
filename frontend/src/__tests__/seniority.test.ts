import {describe, expect, it} from 'vitest';
import {isSeniorTitle} from '../seniority';

describe('isSeniorTitle', () => {
  it.each(['Senior Software Engineer', 'Sr. Engineer', 'Staff Engineer', 'Engineering Manager',
    'Team Leader', 'Head of Data', 'VP, Engineering'])('treats %s as senior', (title) => {
    expect(isSeniorTitle(title)).toBe(true);
  });

  it.each(['Software Engineer III', 'Staffing Coordinator', 'Leading Edge Developer',
    'Data Engineer'])('does not treat %s as senior', (title) => {
    expect(isSeniorTitle(title)).toBe(false);
  });
});
