// Mirrors the backend's JSON exactly, in snake_case. The API has one consumer,
// so there is no camelCase layer.

export type WorkType = 'onsite' | 'hybrid' | 'remote' | 'unknown';
export const WORK_TYPES: WorkType[] = ['onsite', 'hybrid', 'remote', 'unknown'];
export const WORK_TYPE_LABELS: Record<WorkType, string> = {
  onsite: 'On-site',
  hybrid: 'Hybrid',
  remote: 'Remote',
  unknown: 'Unknown',
};

export type EmploymentType = 'full_time' | 'part_time' | 'contract' | 'internship' | 'temporary';
export const EMPLOYMENT_TYPES: EmploymentType[] = [
  'full_time',
  'part_time',
  'contract',
  'internship',
  'temporary',
];
export const EMPLOYMENT_LABELS: Record<EmploymentType, string> = {
  full_time: 'Full-time',
  part_time: 'Part-time',
  contract: 'Contract',
  internship: 'Internship',
  temporary: 'Temporary',
};

export interface Posting {
  id: number;
  posting_key: string;
  board_id: number;
  org: string;
  category: string;
  title: string;
  location: string | null;
  url: string;
  posted_on: string | null;
  posted_age_days: number | null;
  work_type: WorkType;
  employment_type: EmploymentType | null;
  first_seen_at: string;
  is_new: boolean;
  local: boolean;
}

export interface BoardFailure {
  board_id: number;
  org: string;
  error: string | null;
}

export interface PostingsResponse {
  postings: Posting[];
  failures: BoardFailure[];
  scraped_at: string | null;
  refreshing: boolean;
}

export interface PostingsQuery {
  profile?: number;
  maxAgeDays?: number;
  workType?: WorkType[];
  employmentType?: EmploymentType[];
  local?: boolean;
}

export interface PlatformOption {
  kind: 'bool' | 'list';
  help: string;
}

export interface Platform {
  id: string;
  name: string;
  slug_help: string;
  options: Record<string, PlatformOption>;
}

export type BoardOptions = Record<string, boolean | string[]>;

export interface Board {
  id: number;
  platform: string;
  platform_name: string;
  slug: string;
  org: string;
  category: string;
  options: BoardOptions;
  enabled: boolean;
  url: string;
  last_scraped_at: string | null;
  last_status: 'ok' | 'error' | null;
  last_error: string | null;
  last_count: number | null;
}

export interface BoardInput {
  platform: string;
  slug: string;
  org: string;
  category?: string;
  options?: BoardOptions;
  enabled?: boolean;
}

export interface BoardValidation {
  ok: boolean;
  error: string | null;
  count: number;
  sample: string[];
}

export interface Profile {
  id: number;
  name: string;
  include_terms: string[];
  exclude_terms: string[];
  seniority_terms: string[];
  advanced: boolean;
  position: number;
  enabled: boolean;
}

export type ProfileInput = Omit<Profile, 'id' | 'position'>;

export interface Preset {
  key: string;
  name: string;
  description: string;
  include_terms: string[];
  exclude_terms: string[];
  seniority_terms: string[];
  advanced: boolean;
}

export interface Settings {
  max_age_days: number;
  states: string[];
  cities: string[];
  remote: boolean;
  remote_states: string[];
  keep_unknown_location: boolean;
  employment_types: EmploymentType[];
  work_types: WorkType[];
  scrape_interval_hours: number;
  last_full_scrape_at: string | null;
}

export type MarkStatus = 'hidden' | 'not_interested';
export const MARK_LABELS: Record<MarkStatus, string> = {
  hidden: 'Hide',
  not_interested: 'Not interested',
};

export interface Mark {
  posting_key: string;
  status: MarkStatus;
  org: string;
  title: string;
  location: string | null;
  url: string;
  created_at: string;
}
