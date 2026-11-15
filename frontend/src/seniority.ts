// Titles the "Include senior roles" toggle hides when it's off: senior, lead
// and management roles. Whole words, case-insensitive, so "Leading" and
// "Staffing" don't count but "Sr. Engineer" and "Team Leader" do. Level
// numbers ("Engineer III") aren't treated as senior.
const SENIOR_WORDS = [
  'senior',
  'sr\\.?',
  'snr',
  'lead',
  'leader',
  'manager',
  'management',
  'managing',
  'principal',
  'staff',
  'director',
  'head of',
  'chief',
  'vp',
  'svp',
  'evp',
  'vice president',
  'supervisor',
];

const SENIOR_RE = new RegExp(SENIOR_WORDS.map((w) => `\\b${w}(?![\\w])`).join('|'), 'i');

export function isSeniorTitle(title: string): boolean {
  return SENIOR_RE.test(title);
}
