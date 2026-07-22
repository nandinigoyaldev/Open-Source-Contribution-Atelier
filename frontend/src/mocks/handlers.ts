import { http, HttpResponse } from "msw";
import {
  mockAdminDashboardStats,
  mockLeaderboard,
  mockContributorDashboardStats,
  mockCurriculum,
  mockLessonsList,
} from "./fixtures/dashboard";

// Intercepts requests regardless of domain as long as they end in the api paths
const matchUrl = (path: string) => new RegExp(`.*${path}$`);

export const handlers = [
  http.get(matchUrl("/api/dashboard/admin/"), () => {
    return HttpResponse.json(mockAdminDashboardStats);
  }),

  http.get(matchUrl("/api/dashboard/contributor/"), () => {
    return HttpResponse.json(mockContributorDashboardStats);
  }),

  http.get(matchUrl("/api/auth/me/"), () => {
    return HttpResponse.json(null);
  }),

  http.get(matchUrl("/api/leaderboard/"), () => {
    return HttpResponse.json(mockLeaderboard);
  }),

  http.get(matchUrl("/api/content/lessons/"), () => {
    return HttpResponse.json(mockLessonsList);
  }),

  http.get(matchUrl("/content/curriculum.json"), () => {
    return HttpResponse.json(mockCurriculum);
  }),

  http.get(matchUrl("/api/contributors"), () => {
    return HttpResponse.json([]);
  }),

  http.get(matchUrl("/api/progress/me/"), () => {
    return HttpResponse.json([]);
  }),

  http.get(matchUrl("/contributors"), () => {
    return HttpResponse.json([]);
  }),

  http.get(matchUrl("/api/content/organizations/"), () => {
    return HttpResponse.json([]);
  }),

  http.get(matchUrl("/api/users/me/learning-path/"), () => {
    return HttpResponse.json({});
  }),

  http.get(matchUrl("/api/notes/"), () => {
    return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
  }),

  http.get(matchUrl("/api/challenges/today/"), () => {
    return HttpResponse.json(null);
  }),

  http.get(matchUrl("/api/recommendations/"), () => {
    return HttpResponse.json([]);
  }),

  http.get(matchUrl("/api/notifications/"), () => {
    return HttpResponse.json([
      {
        id: 1,
        notif_type: "achievement",
        title: "Welcome",
        message: "You joined the Atelier",
        is_read: false,
        created_at: "2026-07-18T10:00:00Z",
        sender_username: null,
        meta: {},
      },
      {
        id: 2,
        notif_type: "comment",
        title: "New comment",
        message: "Someone replied to your PR",
        is_read: true,
        created_at: "2026-07-17T10:00:00Z",
        sender_username: "mentor",
        meta: {},
      },
    ]);
  }),

  http.post(matchUrl("/api/notifications/1/read/"), () => {
    return HttpResponse.json({
      id: 1,
      notif_type: "achievement",
      title: "Welcome",
      message: "You joined the Atelier",
      is_read: true,
      created_at: "2026-07-18T10:00:00Z",
      sender_username: null,
      meta: {},
    });
  }),

  http.post(matchUrl("/api/notifications/mark-all-read/"), () => {
    return HttpResponse.json({ marked_read: 1 });
  }),

  http.get(matchUrl("/api/notifications/prefs/"), () => {
    return HttpResponse.json({
      email: true,
      in_app: true,
      websocket: true,
    });
  }),

  http.put(matchUrl("/api/notifications/prefs/"), async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      email: Boolean(body.email ?? true),
      in_app: Boolean(body.in_app ?? true),
      websocket: Boolean(body.websocket ?? true),
    });
  }),
];
