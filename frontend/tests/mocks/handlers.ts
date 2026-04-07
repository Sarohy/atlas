import { delay, http, HttpResponse } from 'msw';

export const handlers = [
  http.get('http://localhost:8000/api/v1/health', () => {
    return HttpResponse.json({ status: 'ok', service: 'atlas-backend' });
  }),
  http.post('http://localhost:8000/api/v1/auth/sign-in', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string };
    await delay(150);

    if (body.email === 'admin@atlas.com' && body.password === 'admin@123') {
      return HttpResponse.json({
        email: 'admin@atlas.com',
        message: 'Sign in successful.',
      });
    }

    return HttpResponse.json({ detail: 'Invalid email or password.' }, { status: 401 });
  }),
  http.post('http://localhost:8000/api/v1/auth/logout', async () => {
    await delay(100);

    return HttpResponse.json({
      message: 'Logout successful.',
    });
  }),
];
