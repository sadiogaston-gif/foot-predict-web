export type MarketKey = "home" | "draw" | "away" | "over_2_5" | "under_2_5";

export interface ValueBet {
  market: MarketKey;
  label: string;
  model_probability: number;
  fair_odds: number | null;
  book_odds: number;
  ev_percent: number;
  qualifies: boolean;
}

export interface TopScore {
  score: string;
  probability: number;
}

export interface MatchSummary {
  id: string;
  league_code: string;
  league: string;
  league_long: string;
  country: string;
  date: string | null;
  time: string;
  kickoff: string | null;
  kickoff_utc?: string | null;
  home_team: string;
  away_team: string;
  home_logo?: string | null;
  away_logo?: string | null;
  elo: { home: number; away: number };
  lambdas: { home: number; away: number };
  probabilities: { home: number; draw: number; away: number };
  over_2_5: number;
  under_2_5: number;
  btts_yes: number;
  btts_no: number;
  top_scores: TopScore[];
  odds: Partial<Record<MarketKey, number | null>>;
  fair_odds: Partial<Record<MarketKey, number | null>>;
  value_bets: ValueBet[];
  best_value: ValueBet | null;
  is_value_bet: boolean;
  value_threshold: number;
}

export interface Slate {
  source: string;
  projected: boolean;
  shift_days?: number;
  original_first_date?: string;
  note: string;
  first_date?: string | null;
  last_date?: string | null;
  refreshed_at?: string | null;
  value_bets?: number;
  rows_with_odds?: number | null;
}

export interface UpcomingResponse {
  matches: MatchSummary[];
  count: number;
  slate: Slate;
}

export interface RollingRoi {
  available: boolean;
  window: number;
  bets: number;
  wins: number;
  win_rate: number;
  roi_flat: number;
  roi_kelly: number;
  profit_flat: number;
  profit_kelly: number;
  first_date: string;
  last_date: string;
}

export interface ScoreMatrix {
  goals: number[];
  rows: { goals_home: number; probabilities: number[] }[];
}

export interface EloPoint {
  date: string;
  elo: number;
}

export interface RecentMatch {
  date: string;
  opponent: string;
  venue: "H" | "A";
  goals_for: number;
  goals_against: number;
  result: "W" | "D" | "L";
  league: string;
}

export interface FormSummary {
  played: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  goals_for: number;
  goals_against: number;
  avg_goals_for: number;
  avg_goals_against: number;
}

export interface MatchDetail extends MatchSummary {
  score_matrix: ScoreMatrix;
  elo_history: {
    home: { team: string; points: EloPoint[] };
    away: { team: string; points: EloPoint[] };
  };
  recent: {
    home: { team: string; matches: RecentMatch[]; summary: FormSummary };
    away: { team: string; matches: RecentMatch[]; summary: FormSummary };
  };
  form: {
    home: TeamFormContext;
    away: TeamFormContext;
  };
  external: ExternalContext;
  forces: {
    home: { attack: number; defense: number };
    away: { attack: number; defense: number };
  };
  kelly: { fraction: number; cap_percent: number; bankroll_default: number };
}

export interface FormRecord extends FormSummary {
  goal_difference: number;
  points_per_game: number;
}

export interface TeamFormContext {
  team: string;
  matches: RecentMatch[];
  overall: FormRecord;
  home: FormRecord;
  away: FormRecord;
  clean_sheets: number;
  clean_sheet_rate: number;
  failed_to_score: number;
  btts_count: number;
  btts_rate: number;
  over_2_5_count: number;
  over_2_5_rate: number;
  streak: { type: "W" | "D" | "L" | null; length: number; label: string };
  rest_days: number | null;
  matches_last_14_days: number;
  elo_trend: { current: number; delta_5: number } | null;
}

export interface ExternalSquadPlayer {
  id: number | null;
  name: string;
  age: number | null;
  number: number | null;
  position: string | null;
  photo: string | null;
}

export interface ExternalInjury {
  player: string;
  type: string | null;
  reason: string | null;
  fixture_date: string | null;
  photo: string | null;
}

export interface ExternalLineupTeam {
  team: string;
  formation: string | null;
  coach: string | null;
  startXI: { name: string; number: number | null; position: string | null }[];
}

export interface ExternalRatingPlayer {
  name: string;
  rating: number;
  minutes: number | null;
  position: string | null;
}

export interface ExternalLastRatings {
  team: string;
  date: string | null;
  players: ExternalRatingPlayer[];
}

export interface ExternalStandingRow {
  position: number | null;
  team: string | null;
  team_id: number | null;
  played: number | null;
  points: number | null;
  won: number | null;
  draw: number | null;
  lost: number | null;
  goal_difference: number | null;
  form: string | null;
}

export interface ExternalContext {
  available: boolean;
  provider: string;
  season?: number;
  teams?: {
    home: { id: number; name: string } | null;
    away: { id: number; name: string } | null;
  };
  fixture?: {
    id: number;
    date: string;
    home: string;
    away: string;
    score: { home: number | null; away: number | null };
  } | null;
  squads?: {
    home: ExternalSquadPlayer[] | null;
    away: ExternalSquadPlayer[] | null;
  } | null;
  injuries?: {
    home: ExternalInjury[] | null;
    away: ExternalInjury[] | null;
  } | null;
  lineups?: { teams: ExternalLineupTeam[] } | null;
  ratings?: { teams: { team: string; players: ExternalRatingPlayer[] }[] } | null;
  last_ratings?: {
    home?: ExternalLastRatings | null;
    away?: ExternalLastRatings | null;
  } | null;
  standings?: {
    home: ExternalStandingRow | null;
    away: ExternalStandingRow | null;
  } | null;
  injuries_available?: boolean;
  lineups_available?: boolean;
  ratings_available?: boolean;
  notes?: {
    squads?: string | null;
    injuries?: string | null;
    lineups?: string | null;
    ratings?: string | null;
    standings?: string | null;
  };
  reason: string | null;
}

export interface StrategyStats {
  staked: number;
  profit: number;
  roi_percent: number;
  max_drawdown_units: number;
  max_drawdown_percent: number;
  final_bankroll: number;
}

export interface LeagueRow {
  league: string;
  bets: number;
  wins: number;
  win_rate: number;
  avg_odds: number;
  roi_flat: number;
  profit_flat: number;
  roi_kelly: number;
  profit_kelly: number;
}

export interface MarketRow {
  market: string;
  label: string;
  bets: number;
  win_rate: number;
  avg_odds: number;
  roi_flat: number;
  profit_flat: number;
  roi_kelly: number;
  profit_kelly: number;
}

export interface BankrollPoint {
  index: number;
  date: string;
  label: string;
  flat: number;
  kelly: number;
}

export interface BacktestStats {
  available: boolean;
  season: string;
  warmup_seasons: string[];
  warmup_matches: number;
  matches: number;
  bets: number;
  wins: number;
  win_rate: number;
  avg_odds: number;
  avg_ev: number;
  brier_model: number;
  brier_bookmaker: number;
  brier_baserate: number;
  logloss_model: number;
  accuracy_1x2: number;
  strategy_flat: StrategyStats;
  strategy_kelly: StrategyStats;
  by_league: LeagueRow[];
  by_market: MarketRow[];
  bankroll_curve: BankrollPoint[];
  params: {
    ev_threshold: number;
    min_odds: number;
    max_odds: number;
    initial_bankroll: number;
    kelly_fraction: number;
    kelly_cap: number;
  };
  generated_at: string;
  total_bets_recorded: number;
}

export interface LeagueInfo {
  code: string;
  name: string;
  country: string;
  logo?: string | null;
}

export interface LeaguesResponse {
  leagues: LeagueInfo[];
  value_threshold: number;
}

// ---------------------------------------------------------------------------
// Historique : pronostics vs résultats
// ---------------------------------------------------------------------------
export type OutcomeKey = "home" | "draw" | "away";

export interface HistoryMatch {
  date: string;
  home_team: string;
  away_team: string;
  score: { home: number; away: number };
  probabilities: { home: number; draw: number; away: number };
  predicted: OutcomeKey;
  predicted_probability: number;
  actual: OutcomeKey;
  correct: boolean;
  brier: number;
  odds: Record<OutcomeKey, number | null> | null;
  ev_percent: Record<OutcomeKey, number | null> | null;
  best_value: {
    market: OutcomeKey;
    label: string;
    book_odds: number;
    model_probability: number;
    ev_percent: number;
  } | null;
}

export interface HistorySummary {
  count: number;
  correct: number;
  accuracy_percent: number;
  brier_avg: number;
  value_bets: number;
  value_hits: number;
}

export interface HistoryMatchday {
  date: string;
  date_from: string;
  date_to: string;
  label: string;
  league: string;
  league_name: string;
  matches: HistoryMatch[];
  summary: HistorySummary;
}

export interface HistoryMatchdaysResponse {
  league: string;
  league_name: string;
  limit: number;
  generated_at: string;
  matchdays: {
    date: string;
    date_from: string;
    date_to: string;
    label: string;
    summary: HistorySummary;
  }[];
}
