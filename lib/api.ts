
const API_BASE_URL = 'http://localhost:2467';

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
