import { createClient, SupabaseClient } from "@supabase/supabase-js";

// Custom error class for database errors
export class DatabaseError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly retryable: boolean = false
  ) {
    super(message);
    this.name = "DatabaseError";
  }
}

// Lazy initialization to handle missing env vars gracefully
let supabaseInstance: SupabaseClient | null = null;

function getSupabaseClient(): SupabaseClient {
  if (supabaseInstance) {
    return supabaseInstance;
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new DatabaseError(
      "Database configuration is missing",
      "CONFIG_ERROR",
      false
    );
  }

  supabaseInstance = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: false,
    },
  });

  return supabaseInstance;
}

export const supabase = {
  get client() {
    return getSupabaseClient();
  },
};

const MAX_RETRIES = 2;
const RETRY_DELAY = 500;

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function executeQuery(
  sql: string,
  retryCount = 0
): Promise<Record<string, unknown>[]> {
  // Basic SQL validation - must start with SELECT or WITH (for CTEs)
  const normalizedSql = sql.trim().toUpperCase();
  if (!normalizedSql.startsWith("SELECT") && !normalizedSql.startsWith("WITH")) {
    throw new DatabaseError(
      "Only SELECT queries are allowed",
      "INVALID_QUERY",
      false
    );
  }

  // Check for dangerous patterns (synced with llm.ts validation)
  const dangerousPatterns = [
    /\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b/i,
    /\b(EXEC|EXECUTE|CALL)\b/i,
    /;\s*\w/i, // Multiple statements
    /--/, // SQL comments (potential injection)
    /\/\*/, // Block comments
  ];
  for (const pattern of dangerousPatterns) {
    if (pattern.test(sql)) {
      throw new DatabaseError(
        "Query contains disallowed patterns",
        "INVALID_QUERY",
        false
      );
    }
  }

  try {
    const client = getSupabaseClient();
    const { data, error } = await client.rpc("execute_readonly_query", {
      query_text: sql,
    });

    if (error) {
      // Categorize Supabase errors
      const errorMessage = error.message.toLowerCase();

      // Connection errors are retryable
      if (
        errorMessage.includes("connection") ||
        errorMessage.includes("timeout") ||
        errorMessage.includes("network")
      ) {
        if (retryCount < MAX_RETRIES) {
          console.warn(
            `Database connection error, retrying (attempt ${retryCount + 1}/${MAX_RETRIES})`
          );
          await sleep(RETRY_DELAY * (retryCount + 1));
          return executeQuery(sql, retryCount + 1);
        }
        throw new DatabaseError(
          "Unable to connect to database. Please try again.",
          "CONNECTION_ERROR",
          true
        );
      }

      // Syntax errors
      if (
        errorMessage.includes("syntax") ||
        errorMessage.includes("parse")
      ) {
        throw new DatabaseError(
          "The generated query has a syntax error. Please try rephrasing your question.",
          "SYNTAX_ERROR",
          false
        );
      }

      // Permission errors
      if (
        errorMessage.includes("permission") ||
        errorMessage.includes("denied")
      ) {
        throw new DatabaseError(
          "Access denied for this query",
          "PERMISSION_ERROR",
          false
        );
      }

      // Column/table not found
      if (
        errorMessage.includes("does not exist") ||
        errorMessage.includes("not found")
      ) {
        throw new DatabaseError(
          "Query references invalid table or column. Please try a different question.",
          "INVALID_REFERENCE",
          false
        );
      }

      // Generic database error
      throw new DatabaseError(
        `Query failed: ${error.message}`,
        "QUERY_ERROR",
        false
      );
    }

    // Handle empty results
    if (!data) {
      return [];
    }

    return data as Record<string, unknown>[];
  } catch (error) {
    // Re-throw our custom errors
    if (error instanceof DatabaseError) {
      throw error;
    }

    // Handle unexpected errors
    if (error instanceof Error) {
      // Network/fetch errors are retryable
      if (
        error.message.includes("fetch") ||
        error.message.includes("network")
      ) {
        if (retryCount < MAX_RETRIES) {
          console.warn(
            `Network error, retrying (attempt ${retryCount + 1}/${MAX_RETRIES})`
          );
          await sleep(RETRY_DELAY * (retryCount + 1));
          return executeQuery(sql, retryCount + 1);
        }
      }
      throw new DatabaseError(error.message, "UNKNOWN_ERROR", false);
    }

    throw new DatabaseError(
      "An unexpected database error occurred",
      "UNKNOWN_ERROR",
      false
    );
  }
}

// Health check function
export async function checkDatabaseConnection(): Promise<boolean> {
  try {
    const client = getSupabaseClient();
    const { error } = await client.rpc("execute_readonly_query", {
      query_text: "SELECT 1 as health_check",
    });
    return !error;
  } catch {
    return false;
  }
}

// Cache for date range to avoid repeated queries
let dateRangeCache: { minDate: string; maxDate: string; cachedAt: number } | null = null;
const DATE_RANGE_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export interface DataDateRange {
  minDate: string;
  maxDate: string;
  formatted: string;
}

// Get the actual date range of available data
export async function getDataDateRange(): Promise<DataDateRange> {
  // Return cached value if still valid
  if (dateRangeCache && Date.now() - dateRangeCache.cachedAt < DATE_RANGE_CACHE_TTL) {
    return {
      minDate: dateRangeCache.minDate,
      maxDate: dateRangeCache.maxDate,
      formatted: formatDateRange(dateRangeCache.minDate, dateRangeCache.maxDate),
    };
  }

  try {
    const client = getSupabaseClient();
    const { data, error } = await client.rpc("execute_readonly_query", {
      query_text: "SELECT MIN(date)::text as min_date, MAX(date)::text as max_date FROM daily_sales",
    });

    if (error || !data || data.length === 0) {
      // Fallback to hardcoded range if query fails
      return {
        minDate: "2025-01-01",
        maxDate: "2025-01-04",
        formatted: "January 1-4, 2025",
      };
    }

    const minDate = data[0].min_date;
    const maxDate = data[0].max_date;

    // Update cache
    dateRangeCache = { minDate, maxDate, cachedAt: Date.now() };

    return {
      minDate,
      maxDate,
      formatted: formatDateRange(minDate, maxDate),
    };
  } catch {
    // Fallback to hardcoded range if query fails
    return {
      minDate: "2025-01-01",
      maxDate: "2025-01-04",
      formatted: "January 1-4, 2025",
    };
  }
}

// Format date range for human-readable display
function formatDateRange(minDate: string, maxDate: string): string {
  const min = new Date(minDate + "T00:00:00");
  const max = new Date(maxDate + "T00:00:00");

  const minMonth = min.toLocaleDateString("en-US", { month: "long" });
  const maxMonth = max.toLocaleDateString("en-US", { month: "long" });
  const minDay = min.getDate();
  const maxDay = max.getDate();
  const minYear = min.getFullYear();
  const maxYear = max.getFullYear();

  // Same month and year
  if (minMonth === maxMonth && minYear === maxYear) {
    return `${minMonth} ${minDay}-${maxDay}, ${minYear}`;
  }

  // Same year, different months
  if (minYear === maxYear) {
    return `${minMonth} ${minDay} - ${maxMonth} ${maxDay}, ${minYear}`;
  }

  // Different years
  return `${minMonth} ${minDay}, ${minYear} - ${maxMonth} ${maxDay}, ${maxYear}`;
}
