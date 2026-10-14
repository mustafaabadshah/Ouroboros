export interface Repository {
  id: string;
  name: string;
  path: string;
  is_valid: boolean;
  commit_hash?: string;
  indexed_at?: string;
  file_count: number;
  warnings: string[];
  created_at: string;
}

export interface GraphStatus {
  repo_id: string;
  backend_mode: string;
  connected: boolean;
  node_count: number;
  edge_count: number;
  source_index_file?: string;
  message: string;
}

export interface Ticket {
  id: string;
  repo_id: string;
  title: string;
  problem_statement: string;
  motivation: string;
  current_behavior: string;
  desired_behavior: string;
  acceptance_criteria: string[];
  proposed_tests: string[];
  relevant_graph_entities: string[];
  candidate_files: string[];
  risk_level: string;
  expected_complexity: string;
  estimated_resources: string;
  evidence: string[];
  out_of_scope?: string;
  status: string; // PROPOSED, REVIEWED, APPROVED, IMPLEMENTING, EVALUATING, ACCEPTED, REJECTED
  created_at: string;
  updated_at: string;
}

export interface Run {
  id: string;
  ticket_id: string;
  repo_id: string;
  state: string; // IDLE, REPOSITORY_ANALYSIS, TICKET_GENERATION, ..., AWAITING_APPROVAL, COMPLETED, FAILED
  active_agent?: string;
  active_provider?: string;
  active_model?: string;
  base_commit?: string;
  candidate_branch?: string;
  retry_count: number;
  max_retries: number;
  verdict?: string;
  error_message?: string;
  started_at: string;
  completed_at?: string;
}

export interface TestResult {
  id: string;
  run_id: string;
  candidate_id?: string;
  test_type: string;
  test_command: string;
  exit_code: number;
  duration_ms: number;
  passed_count: number;
  failed_count: number;
  error_count: number;
  failures: Array<{ test_name: string; traceback: string }>;
  stdout_excerpt?: string;
  stderr_excerpt?: string;
  created_at: string;
}

export interface DiffInspection {
  run_id: string;
  candidate_id?: string;
  attempt: number;
  diff_content: string;
  diff_hash: string;
  patch_explanation?: string;
  changed_files: string[];
  lines_added: number;
  lines_removed: number;
  ast_changes: Record<string, any>;
  protected_files_affected: string[];
  verdict?: string;
}

export interface FailureTrajectory {
  id: string;
  run_id: string;
  ticket_id: string;
  attempt: number;
  provider?: string;
  model?: string;
  failed_tests: string[];
  traceback_excerpt?: string;
  ast_diff: Record<string, any>;
  patch_hash?: string;
  root_cause_hypothesis?: string;
  repair_hint?: string;
  status: string; // UNRESOLVED, REPAIRED, REPEATED
  created_at: string;
}

export interface ModelStatus {
  local_runtime: string;
  local_available: boolean;
  installed_models: string[];
  default_local_model: string;
  active_local_model?: string;
  groq_available: boolean;
  groq_masked_key: string;
  groq_reasoning_model: string;
  groq_fast_model: string;
  allow_remote_fallback: boolean;
  require_fallback_confirmation: boolean;
  current_free_ram_mb: number;
  ram_warning: boolean;
}

export interface MetricsOverview {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  acceptance_rate: number;
  total_trajectories: number;
  avg_run_duration_sec: number;
  free_ram_mb: number;
  total_ram_mb: number;
  cpu_percent: number;
  docker_available: boolean;
  ollama_available: boolean;
  groq_available: boolean;
}

export interface SystemSettings {
  app_name: string;
  theme: string;
  log_level: string;
  default_repo_path: string;
  navigator_path: string;
  max_local_concurrency: number;
  max_test_concurrency: number;
  memory_warning_threshold_mb: number;
  max_repair_attempts: number;
  max_tickets_per_batch: number;
  require_ticket_approval: boolean;
  require_remote_fallback_confirmation: boolean;
  require_merge_approval: boolean;
  sandbox_mode: string;
  subprocess_timeout_seconds: number;
}
