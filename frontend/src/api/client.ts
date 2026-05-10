import type { ApiError } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export class ApiClientError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(status: number, body: ApiError) {
    super(body.message || body.code);
    this.code = body.code;
    this.status = status;
    this.details = body.details;
  }
}

async function parseError(res: Response): Promise<never> {
  let body: ApiError = { code: "INTERNAL_ERROR", message: res.statusText };
  try {
    body = await res.json();
  } catch {
    // 응답이 JSON이 아닐 수 있음
  }
  throw new ApiClientError(res.status, body);
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { method: "GET" });
  if (!res.ok) await parseError(res);
  return res.json() as Promise<T>;
}

export async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) await parseError(res);
  return res.json() as Promise<T>;
}

export function audioUrl(path: string): string {
  return `${BASE_URL}${path}`;
}
