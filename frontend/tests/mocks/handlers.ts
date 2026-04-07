import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('http://localhost:8000/api/v1/health', () => {
    return HttpResponse.json({ status: 'ok', service: 'atlas-backend' });
  }),
];
