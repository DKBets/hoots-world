/* Hoot family accounts: where the account service lives.
   Leave both values empty and the app works exactly as before (no accounts).
   To switch accounts on, paste the two values from your Supabase project:
   Project Settings -> API -> "Project URL" and the "anon public" key.
   The anon key is safe to publish: the database rules decide what it can do.
   NEVER paste the "service_role" key here. */
window.HOOT_BACKEND = window.HOOT_BACKEND || {
  url: "",
  anonKey: ""
  /* Photos stay on each device while accounts are on; they are not uploaded. */
};
