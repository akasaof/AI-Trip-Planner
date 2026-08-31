const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Request to ${path} failed (${res.status}): ${body}`);
  }
  return res.json();
}

export const api = {
  createTrip: (message) =>
    request("/api/trips", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  chat: (tripId, message) =>
    request(`/api/trips/${tripId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  getMessages: (tripId) => request(`/api/trips/${tripId}/messages`),

  getTrip: (tripId) => request(`/api/trips/${tripId}`),
};
