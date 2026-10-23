// Anonymous player identity (v1 has no accounts). Set by proxy.ts, forwarded to the agent by the runtime route.
export const SESSION_COOKIE = "la_session";
export const SESSION_MAX_AGE = 60 * 60 * 24 * 30;
