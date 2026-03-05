import type { Watch, CreateWatchRequest, UpdateWatchRequest, ApiError } from './types';

const BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiClientError extends Error {
  constructor(public status: number, public details: ApiError) {
    const msg = details.errors?.join(', ') || details.error || 'Unknown error';
    super(msg);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });

  if (resp.status === 204) return undefined as T;

  const data = await resp.json();
  if (!resp.ok) throw new ApiClientError(resp.status, data);
  return data as T;
}

export async function createWatch(body: CreateWatchRequest): Promise<Watch> {
  return request<Watch>('/watches', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function listWatches(phone: string): Promise<Watch[]> {
  const data = await request<{ watches: Watch[] }>(
    `/watches?phone=${encodeURIComponent(phone)}`
  );
  return data.watches;
}

export async function getWatch(id: string, phone: string): Promise<Watch> {
  return request<Watch>(
    `/watches/${id}?phone=${encodeURIComponent(phone)}`
  );
}

export async function updateWatch(id: string, body: UpdateWatchRequest): Promise<Watch> {
  return request<Watch>(`/watches/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteWatch(id: string, phone: string): Promise<void> {
  return request<void>(
    `/watches/${id}?phone=${encodeURIComponent(phone)}`,
    { method: 'DELETE' }
  );
}

export { ApiClientError };
