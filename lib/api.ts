
const API_BASE_URL = 'http://34.66.204.223:2467';

export async function login(userId: string) {
  const response = await fetch(`${API_BASE_URL}/api/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ user_id: userId }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || 'Login failed');
  }
  return data;
}

export async function greet() {
  const response = await fetch(`${API_BASE_URL}/api/greet`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Greeting failed');
  }
  return response.json();
}

export async function sendMessage(message: string) {
  const response = await fetch(`${API_BASE_URL}/api/send`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    throw new Error('Sending message failed');
  }
  return response.json();
}

type ProfileResponse = {
  ok: boolean;
  profile?: {
    age: number | null;
    height_cm: number | null;
    weight_kg: number | null;
    underlying_disease: string | null;
  };
  error?: string;
};

type SessionResponse = {
  ok: boolean;
  user_id?: number;
  error?: string;
};

type ForecastApiResponse = {
  ok: boolean;
  forecast?: {
    minutes: number[];
    absolute_glucose: number[];
    delta_glucose: number[];
    inputs_used: Record<string, unknown>;
  };
  error?: string;
};

export async function fetchProfile() {
  const response = await fetch(`${API_BASE_URL}/api/profile`, {
    method: 'GET',
    credentials: 'include',
  });
  const data: ProfileResponse = await response.json().catch(() => ({ ok: false } as ProfileResponse));
  if (!response.ok || !data.ok || !data.profile) {
    throw new Error(data.error || 'Failed to load profile');
  }
  return data.profile;
}

export async function updateProfile(payload: {
  age: number;
  height_cm: number;
  weight_kg: number;
  underlying_disease: string;
}) {
  const response = await fetch(`${API_BASE_URL}/api/profile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  });
  const data: ProfileResponse = await response.json().catch(() => ({ ok: false } as ProfileResponse));
  if (!response.ok || !data.ok || !data.profile) {
    throw new Error(data.error || 'Failed to save profile');
  }
  return data.profile;
}

export async function getSession() {
  const response = await fetch(`${API_BASE_URL}/api/session`, {
    method: 'GET',
    credentials: 'include',
  });
  const data: SessionResponse = await response.json().catch(() => ({ ok: false } as SessionResponse));
  if (!response.ok || !data.ok || typeof data.user_id !== 'number') {
    throw new Error(data.error || 'Not authenticated');
  }
  return data.user_id;
}

type ForecastPayload = {
  height_cm: number;
  weight_kg: number;
  age?: number | null;
  gender?: string | null;
  baseline_avg_glucose?: number | null;
  meal_bucket?: string | null;
};

export async function fetchForecast(payload: ForecastPayload) {
  const body: Record<string, unknown> = {
    height_cm: payload.height_cm,
    weight_kg: payload.weight_kg,
  };

  if (payload.age != null) {
    body.age = payload.age;
  }
  if (payload.gender) {
    body.gender = payload.gender;
  }
  if (payload.baseline_avg_glucose != null) {
    body.baseline_avg_glucose = payload.baseline_avg_glucose;
  }
  if (payload.meal_bucket) {
    body.meal_bucket = payload.meal_bucket;
  }

  const response = await fetch(`${API_BASE_URL}/api/predict`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(body),
  });

  const data: ForecastApiResponse = await response.json().catch(() => ({ ok: false } as ForecastApiResponse));
  if (!response.ok || !data.ok || !data.forecast) {
    throw new Error(data.error || 'Failed to load forecast');
  }
  return data.forecast as NonNullable<ForecastApiResponse["forecast"]>;
}
