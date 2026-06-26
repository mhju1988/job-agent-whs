import { createClient } from "@supabase/supabase-js";
import { ENV } from "./env";

/** Browser Supabase client (singleton). Auth only — data goes through the API. */
export const supabase = createClient(ENV.supabaseUrl, ENV.supabaseAnonKey, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
});
