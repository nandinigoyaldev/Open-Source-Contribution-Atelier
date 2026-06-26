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
];
