/** Response shapes mirroring the FastAPI backend (src/job_agent/api). */

export interface Me {
  user_id: string;
  profile_label: string;
  has_profile: boolean;
  scout_sources: string[];
}

export interface ProfileExperience {
  title: string;
  company: string;
  start?: string | null;
  end?: string | null;
  description?: string | null;
}

export interface ProfileEducation {
  degree: string;
  institution: string;
  field?: string | null;
  start?: string | null;
  end?: string | null;
  description?: string | null;
}

export interface Profile {
  id?: string;
  full_name?: string | null;
  summary?: string | null;
  skills?: string[];
  experience?: ProfileExperience[];
  education?: ProfileEducation[];
  languages?: string[];
}

export interface Job {
  id: string;
  source: string;
  title: string;
  company: string | null;
  location: string | null;
  url: string | null;
  scraped_at: string;
}

/** Job enriched with the user's match score (null = not yet scored). */
export type JobWithScore = Job & {
  score: number | null;
  match_id: string | null;
};

export interface MatchApplication {
  id: string;
  status: ApplicationStatus;
  cover_letter_path: string | null;
}

export interface MatchJob {
  title: string | null;
  company: string | null;
  /** Nested join through jobs: the application row (if any) for this job.
   *  PostgREST returns it as a 0-or-1 element array; RLS scopes it to the
   *  current user. */
  applications?: MatchApplication[] | null;
}

export interface Match {
  id: string;
  job_id: string;
  score: number | null;
  matched_skills: string[] | null;
  gaps: string[] | null;
  rationale: string | null;
  created_at: string | null;
  jobs?: MatchJob | null;
}

/**
 * A job surfaced for the fit-graph, carrying BOTH scoring stages so the two
 * canvases (Stage 1 cosine / Stage 2 LLM) can share one job set.
 *  - similarity: stage-1 cosine similarity, 0..1 (null when the job has no
 *    embedding — e.g. scored via the manual "score these" path — so the job
 *    is dropped from the Stage-1 canvas but still shows in Stage 2)
 *  - score:      stage-2 LLM fit, 0..100 (always present in the graph payload,
 *    which is sourced from match_scores)
 */
export interface GraphJob {
  job_id: string;
  title: string;
  company: string | null;
  similarity: number | null;
  score: number | null;
  requirements: string[];
  description: string | null;
  matched_skills: string[];
  gaps: string[];
  rationale: string | null;
}

export interface MatchGraph {
  profile: { skills: string[] } | null;
  jobs: GraphJob[];
}

export type ApplicationStatus =
  | "new"
  | "ready_to_send"
  | "applied"
  | "interview"
  | "offer"
  | "rejected";

export interface Application {
  id: string;
  job_id: string | null;
  job_title: string | null;
  job_company: string | null;
  status: ApplicationStatus;
  cover_letter_path: string | null;
  cv_variant_path: string | null;
  follow_up_at: string | null;
  applied_at: string | null;
}

export interface CvUploadResult {
  ok: boolean;
  error: string | null;
  rescored: number | null;
}

export interface DeleteSummary {
  profiles_deleted: number;
  matches_deleted: number;
  applications_deleted: number;
  files_deleted: number;
}

export interface ObsRun {
  run_id: string;
  agent_name: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  error_message?: string | null;
}

export interface ObsEvent {
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  duration_ms?: number | null;
  estimated_cost_eur?: number | null;
  prompt_snippet?: string | null;
  response_snippet?: string | null;
  [k: string]: unknown;
}

/** SSE progress event (shape varies by stage). */
export interface ProgressEvent {
  stage: string;
  current?: number;
  total?: number;
  source?: string;
  [k: string]: unknown;
}

export type RunKind = "scout" | "matcher" | "scout-matcher" | "writer" | "rescore";

export interface SearchSuggestion {
  keyword: string;
  location: string | null;
  rationale: string | null;
}

export interface AdminUser {
  id: string;
  email: string | null;
  created_at: string;
  email_confirmed: boolean;
  banned: boolean;
  role: string;
}
