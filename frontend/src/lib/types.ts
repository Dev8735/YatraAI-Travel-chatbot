// Types mirroring the FastAPI schemas (backend/app/schemas).

export type DataOrigin = "live" | "demo";

export interface Attribution { name: string; uri?: string | null }
export interface PhotoRef { url: string; width?: number | null; height?: number | null; attributions: Attribution[] }

export interface Place {
  id: string;
  name: string;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  category?: string | null;
  types: string[];
  tags: string[];
  rating?: number | null;
  user_rating_count?: number | null;
  price_level?: string | null;
  opening_hours: string[];
  open_now?: boolean | null;
  photos: PhotoRef[];
  maps_url?: string | null;
  website?: string | null;
  destination?: string | null;
  typical_visit_minutes?: number | null;
  data_origin: DataOrigin;
  provider: string;
  provider_attribution?: string | null;
}

export interface PlaceSearchResult { query: string; places: Place[]; provider: string; data_origin: DataOrigin; notice?: string | null }

export type TravelMode = "DRIVE" | "WALK" | "BICYCLE" | "TWO_WHEELER" | "TRANSIT";

export interface RouteLeg { start: string; end: string; distance_meters?: number | null; duration_seconds?: number | null }
export interface RouteResult {
  available: boolean;
  provider: string;
  travel_mode: TravelMode;
  origin: string;
  destination: string;
  stops: string[];
  distance_meters?: number | null;
  duration_seconds?: number | null;
  summary?: string | null;
  legs: RouteLeg[];
  warnings: string[];
  straight_line_km?: number | null;
  notice?: string | null;
  retrieved_at?: string | null;
}

export interface OfficialLink { label: string; url: string }
export interface TransportInfo { provider: string; available: boolean; mode?: string | null; origin?: string | null; destination?: string | null; message: string; official_links: OfficialLink[] }

export interface Stop {
  id: string;
  place: Place;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  transfer_minutes_before?: number | null;
  transfer_is_estimate: boolean;
  reason: string;
  notes: string[];
  hours_verified: boolean;
}
export interface Break { time: string; label: string; duration_minutes: number }
export interface Day { day: number; date?: string | null; title: string; stops: Stop[]; breaks: Break[]; notes: string[] }

export type BudgetTier = "budget" | "mid" | "luxury";
export type Pace = "relaxed" | "balanced" | "packed";

export interface Money { amount: number; currency: string; qualifier: "max" | "approx" | "min"; per_person: boolean }

export interface BudgetEstimate {
  tier: BudgetTier;
  currency: string;
  per_person_per_day_min: number;
  per_person_per_day_max: number;
  days: number;
  travellers: number;
  travellers_assumed: boolean;
  total_min: number;
  total_max: number;
  user_budget?: Money | null;
  within_user_budget: "yes" | "no" | "partly" | "unknown";
  basis: string;
  excludes: string[];
  source_url?: string | null;
}

export interface ItineraryPlan {
  destination: string;
  days: Day[];
  unplaced: Place[];
  excluded_place_ids: string[];
  assumptions: string[];
  warnings: string[];
  budget_estimate?: BudgetEstimate | null;
  data_origin: DataOrigin;
  provider: string;
  generated_at: string;
}

export interface ItineraryRequest {
  destination: string;
  origin?: string | null;
  start_date?: string | null;
  days: number;
  travellers?: number | null;
  budget?: Money | null;
  budget_level?: BudgetTier | null;
  interests: string[];
  pace: Pace;
  transport_mode?: string | null;
  accommodation: string[];
  accessibility: string[];
}

export interface Itinerary {
  id: string;
  title: string;
  conversation_id?: string | null;
  request: ItineraryRequest;
  plan: ItineraryPlan;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ItinerarySummary { id: string; title: string; destination: string; days: number; version: number; updated_at: string }

export type ItineraryOperation =
  | { op: "remove_stop"; stop_id: string }
  | { op: "add_stop"; day: number; place_id: string }
  | { op: "move_stop"; stop_id: string; to_day: number; position?: number | null }
  | { op: "replace_stop"; stop_id: string; place_id: string }
  | { op: "add_day" }
  | { op: "remove_day"; day: number }
  | { op: "regenerate_day"; day: number }
  | { op: "update_preferences"; pace?: Pace; interests?: string[]; budget_level?: BudgetTier; travellers?: number }
  | { op: "rename"; title: string };

export interface Citation {
  id: string;
  url: string;
  title: string;
  heading?: string | null;
  snippet: string;
  is_demo: boolean;
  fetched_at?: string | null;
  published_at?: string | null;
}

export interface RecommendationItem { name: string; state: string; country: string; matched_interests: string[]; reasons: string[]; guide_url?: string | null; straight_line_km?: number | null }
export interface ComparisonItem { name: string; landscape: string; known_for: string[]; matched_interests: string[]; suggested_days: string; fits_days?: boolean | null; straight_line_km?: number | null; guide_url?: string | null }

export type Block =
  | { type: "places"; result: PlaceSearchResult }
  | { type: "itinerary"; itinerary_id: string; title: string; version: number; plan: ItineraryPlan; changes: string[] }
  | { type: "route"; route: RouteResult }
  | { type: "recommendations"; criteria: string[]; items: RecommendationItem[]; note: string }
  | { type: "comparison"; criteria: string[]; items: ComparisonItem[]; note: string }
  | { type: "budget"; estimate: BudgetEstimate }
  | { type: "transport"; info: TransportInfo }
  | { type: "clarify"; question: string; missing: string[]; options: string[] };

export type Evidence = "strong" | "limited" | "none";

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  user_message_id: string;
  answer: string;
  language: string;
  intent: string;
  classifier: string;
  entities: Record<string, unknown>;
  citations: Citation[];
  evidence?: Evidence | null;
  answer_mode: "llm" | "extractive" | "template" | "none";
  blocks: Block[];
  suggestions: string[];
  notices: string[];
}

export interface MessageMeta {
  citations?: Citation[];
  evidence?: Evidence | null;
  answer_mode?: ChatResponse["answer_mode"];
  blocks?: Block[];
  suggestions?: string[];
  notices?: string[];
  intent?: string;
  language?: string;
}

export interface MessageOut { id: string; role: "user" | "assistant"; content: string; created_at: string; metadata: MessageMeta }
export interface ConversationSummary { id: string; title: string; created_at: string; updated_at: string }
export interface ConversationDetail extends ConversationSummary { messages: MessageOut[]; context: Record<string, unknown> }
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }

export interface JobOut {
  id: string;
  source_id: string;
  status: "queued" | "running" | "succeeded" | "partial" | "failed";
  pages_discovered: number;
  pages_fetched: number;
  pages_indexed: number;
  pages_unchanged: number;
  pages_skipped: number;
  pages_failed: number;
  chunks_indexed: number;
  errors: { url: string; reason: string }[];
  message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface SourceOut {
  id: string;
  url: string;
  domain: string;
  title?: string | null;
  status: "pending" | "running" | "ready" | "partial" | "failed";
  is_demo: boolean;
  max_pages: number;
  max_depth: number;
  page_count: number;
  chunk_count: number;
  last_error?: string | null;
  last_ingested_at?: string | null;
  created_at: string;
  latest_job?: JobOut | null;
}

export interface DemoDoc { slug: string; title: string; url: string; body?: string }

export interface Health {
  status: "ok" | "degraded";
  environment: string;
  demo_mode: boolean;
  components: {
    database: { ok: boolean; engine: string };
    vector_store: { ok: boolean; mode: string; collection: string };
    embeddings: { name: string; dim: number; multilingual: boolean };
    llm: { provider: string; model: string; live: boolean };
    places: { provider: string; live: boolean };
    routes: { provider: string; live: boolean };
    transport: { provider: string; live: boolean };
  };
}

export interface ApiErrorBody { error: { code: string; message: string; details?: Record<string, unknown>; request_id?: string } }
