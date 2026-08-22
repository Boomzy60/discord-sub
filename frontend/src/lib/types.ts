export interface User {
  id: string;
  discord_id: string;
  username: string;
  global_name: string | null;
  avatar: string | null;
  email: string | null;
  is_admin: boolean;
  created_at: string;
}

export interface ApiEnvelope<T> {
  success: boolean;
  data: T | null;
  error: unknown;
}

export interface CryptoCurrency {
  code: string;
  label: string;
}

export interface Tier {
  id: string;
  name: string;
  description: string | null;
  price: number;
  currency: string;
  duration_days: number;
  active: boolean;
  display_order: number;
  discord_role_id: string;
  created_at: string;
}
