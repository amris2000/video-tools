export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,

    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;

    try {
      const data = await response.json();

      if (data.error) {
        message = data.error;
      }

      if (data.detail) {
        message = data.detail;
      }
    } catch {
      // Response was not JSON.
    }

    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}
