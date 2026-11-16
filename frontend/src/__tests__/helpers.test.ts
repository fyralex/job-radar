import {describe, expect, it} from 'vitest';
import {matchesText, parseTerms, refreshNotice, splitList, toggle} from '../lib';
import {postingsParams} from '../redux/api';
import {posting} from './factories';

describe('matchesText', () => {
  const p = posting({title: 'Senior Data Engineer', org: 'Acme', location: 'Austin, TX'});
  it('needs every word somewhere in title, org or location', () => {
    expect(matchesText(p, 'data austin')).toBe(true);
    expect(matchesText(p, '  ')).toBe(true);
    expect(matchesText(p, 'data denver')).toBe(false);
  });
});

describe('form helpers', () => {
  it('parses one term per line', () => {
    expect(parseTerms(' react \n\nfull stack\n')).toEqual(['react', 'full stack']);
  });
  it('splits cities on semicolons and newlines', () => {
    expect(splitList('Austin, TX; Denver, CO\nBoise, ID')).toEqual([
      'Austin, TX',
      'Denver, CO',
      'Boise, ID',
    ]);
  });
});

describe('postingsParams', () => {
  it('only sends what is set', () => {
    expect(postingsParams({})).toEqual({});
    expect(
      postingsParams({profile: 2, maxAgeDays: 7, workType: ['remote', 'hybrid'], local: true}),
    ).toEqual({profile: '2', maxAgeDays: '7', workType: 'remote,hybrid', local: 'true'});
  });
});

describe('toggle', () => {
  it('adds or removes a value', () => {
    expect(toggle(['a'], 'b')).toEqual(['a', 'b']);
    expect(toggle(['a', 'b'], 'a')).toEqual(['b']);
  });
});

describe('refreshNotice', () => {
  it('says nothing when a run started', () => {
    expect(refreshNotice({started: true, refreshing: true, reason: null}, undefined)).toBeNull();
    expect(refreshNotice(undefined, undefined)).toBeNull();
  });

  it('explains why a run did not start', () => {
    expect(
      refreshNotice({started: false, refreshing: true, reason: 'already_running'}, undefined),
    ).toMatch(/already running/);
    expect(
      refreshNotice({started: false, refreshing: false, reason: 'unavailable'}, undefined),
    ).toMatch(/unavailable right now/);
  });

  it('shows a request error', () => {
    expect(refreshNotice(undefined, {status: 500, data: {error: 'boom'}})).toBe(
      'Couldn’t start a refresh: boom',
    );
  });
});
