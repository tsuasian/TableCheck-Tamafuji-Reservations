export interface Watch {
  watch_id: string;
  phone: string;
  name: string | null;
  email: string | null;
  dates: string[];
  party_size: number;
  preferred_times: string[] | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateWatchRequest {
  name: string;
  email: string;
  phone: string;
  dates: string[];
  party_size: number;
  preferred_times: string[] | null;
}

export interface UpdateWatchRequest {
  phone: string;
  name?: string;
  email?: string;
  dates?: string[];
  party_size?: number;
  preferred_times?: string[] | null;
  is_active?: boolean;
}

export interface ApiError {
  error?: string;
  errors?: string[];
}
