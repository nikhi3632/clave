/**
 * API base URL configuration.
 * Uses NEXT_PUBLIC_API_URL env var if set, otherwise falls back to local Next.js API routes.
 *
 * For local development with Next.js API routes: leave NEXT_PUBLIC_API_URL unset
 * For decoupled FastAPI backend: set NEXT_PUBLIC_API_URL=http://localhost:8000
 * For production: set NEXT_PUBLIC_API_URL=https://your-api-domain.com
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Build full API endpoint URL.
 * @param path - API path (e.g., "/api/query")
 * @returns Full URL
 */
export function getApiUrl(path: string): string {
  // If API_URL is set, use it; otherwise use relative path for Next.js API routes
  if (API_URL) {
    return `${API_URL}${path}`;
  }
  return path;
}
