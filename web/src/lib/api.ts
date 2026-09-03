/** Thin client for the portfolio API. */

import type { AnalyzeRequest, AnalyzeResponse, SearchResult } from "./types";

// Vite proxies /api to the backend in development; in production the app is
// served from the same origin, so a relative base works in both cases.
const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(
      "Could not reach the analysis API. Is the backend running on port 8000?",
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await describeError(response), response.status);
  }
  return (await response.json()) as T;
}

/**
 * FastAPI reports validation failures as a list of field errors and other
 * failures as a plain string. Flatten both into one readable sentence.
 */
async function describeError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          const field = Array.isArray(item?.loc) ? item.loc.slice(1).join(".") : "";
          const message = item?.msg ?? "invalid value";
          return field ? `${field}: ${message}` : message;
        })
        .join("; ");
    }
  } catch {
    // Fall through to the generic message below.
  }
  return `Request failed (${response.status})`;
}

export function analyzePortfolio(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/api/portfolio/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function searchTickers(query: string): Promise<SearchResult[]> {
  return request<SearchResult[]>(`/api/search?q=${encodeURIComponent(query)}`);
}
