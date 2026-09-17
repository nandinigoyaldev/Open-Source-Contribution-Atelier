import React, { useState } from "react";
import {
  BookOpen,
  Cpu,
  Layers,
  Search,
  Server,
  Terminal,
  Code,
  Globe,
  CheckCircle2,
  ExternalLink,
  ArrowRight,
  Zap,
} from "lucide-react";
import { Link } from "react-router-dom";
import { FAQAccordion } from "../../components/docs/FAQAccordion";
import CopyButton from "../../components/ui/CopyButton";
import { CARD_FOCUS_RING } from "../../lib/a11yFocus";
import { useMarkdownWorker } from "../../hooks/useMarkdownWorker";

interface TechComponent {
  name: string;
  category:
    | "frontend"
    | "backend"
    | "database"
    | "async"
    | "security"
    | "realtime";
  description: string;
  technologies: string[];
  features: string[];
  endpointOrPath: string;
}

const REPO_FEATURES: TechComponent[] = [
  {
    name: "Interactive Learning & Content Studio",
    category: "frontend",
    description:
      "Curriculum viewer, interactive quiz runner, markdown renderer, and teacher content draft studio.",
    technologies: ["React 19", "KaTeX", "Vite", "Django REST"],
    features: [
      "Step-by-step progress",
      "Quiz builder & validation",
      "Live Markdown preview",
      "XP awards on completion",
    ],
    endpointOrPath: "/learning-path",
  },
  {
    name: "Contributor Sandbox & Code Execution Engine",
    category: "frontend",
    description:
      "Browser & server-side isolated code execution playground supporting multi-language snippet testing.",
    technologies: ["Monaco Editor", "Web Workers", "Docker", "Pyodide"],
    features: [
      "Live stdout/stderr capture",
      "Lint error highlighting",
      "Theme customization",
      "Snippet export",
    ],
    endpointOrPath: "/contributor-sandbox",
  },
  {
    name: "Audit Log Inspector & Domain Ledger",
    category: "security",
    description:
      "Immutable domain event ledger tracking created, updated, and deleted model snapshots with JSON state diffs.",
    technologies: ["Django Audit Model", "PostgreSQL JSONB", "Tailwind UI"],
    features: [
      "Before/after state diff",
      "Search & filter",
      "Actor & correlation tracking",
      "CSV/JSON export",
    ],
    endpointOrPath: "/admin/audit",
  },
  {
    name: "Celery Distributed Task Worker Queue",
    category: "async",
    description:
      "Asynchronous background job worker handling PDF generation, webhook dispatches, and issue quality scans.",
    technologies: [
      "Celery",
      "Redis Broker",
      "WebSocket Push",
      "Django Monitoring",
    ],
    features: [
      "Queue depth monitoring",
      "Worker health gauges",
      "24h execution sparklines",
      "Live task triggers",
    ],
    endpointOrPath: "/admin/celery",
  },
  {
    name: "OAuth 2.0 & OpenID Connect Provider",
    category: "security",
    description:
      "RFC 7636 PKCE compliant OAuth 2.0 authorization server issuing JWT access and refresh tokens to client apps.",
    technologies: [
      "Django OAuth Toolkit",
      "SimpleJWT",
      "PyJWT",
      "OIDC Provider",
    ],
    features: [
      "Client Registration",
      "Public (PKCE) & Confidential types",
      "Allowed Redirect URIs",
      "Grant Scopes",
    ],
    endpointOrPath: "/admin/oauth-clients",
  },
  {
    name: "Git Rebase Simulator & PR Diff Summarizer",
    category: "frontend",
    description:
      "Interactive visualizer for Git branch merging, rebase conflict resolution, and automated PR diff summarization.",
    technologies: ["Git Graph UI", "Mermaid.js", "AI Summarizer"],
    features: [
      "Interactive graph manipulation",
      "Step-by-step rebase guide",
      "Diff highlighting",
      "Conflict resolution sandbox",
    ],
    endpointOrPath: "/git-rebase-simulator",
  },
  {
    name: "Skill Tree, XP Shop & Contributor Rankings",
    category: "realtime",
    description:
      "Gamified learning progression tree with unlockable nodes, XP store rewards, and real-time contributor rankings.",
    technologies: ["Cytoscape.js", "Recharts", "WebSockets"],
    features: [
      "Interactive node tree",
      "XP purchase system",
      "Global rankings",
      "Streak multiplier calculation",
    ],
    endpointOrPath: "/skill-tree",
  },
  {
    name: "Live Notes, Community Chat & Peer Review",
    category: "realtime",
    description:
      "Collaborative markdown notebook, real-time community chat channels, and pull request peer review platform.",
    technologies: ["Django Channels", "WebSockets", "Lucide React"],
    features: [
      "Real-time document sync",
      "Chat channel switching",
      "Code review comments",
      "Notification badges",
    ],
    endpointOrPath: "/collab-notes",
  },
];

const API_ENDPOINTS = [
  {
    method: "GET",
    path: "/api/content/lessons/",
    desc: "List all curriculum modules and lessons",
  },
  {
    method: "POST",
    path: "/api/auth/token/",
    desc: "Obtain JWT Access & Refresh Token pair",
  },
  {
    method: "GET",
    path: "/api/admin/audit/",
    desc: "Search & filter domain audit event logs",
  },
  {
    method: "GET",
    path: "/api/admin/celery-stats/",
    desc: "Fetch live Celery worker & queue metrics",
  },
  {
    method: "POST",
    path: "/api/oauth/clients/",
    desc: "Register new OAuth 2.0 application client",
  },
  {
    method: "GET",
    path: "/api/leaderboard/",
    desc: "Retrieve global contributor XP rankings",
  },
  {
    method: "GET",
    path: "/health/",
    desc: "Comprehensive system component health checks",
  },
];

const HERO_INTRO_MARKDOWN =
  "Explore **interactive architecture guides**, `Django REST` API endpoint specs, **Celery** worker queues, `OAuth 2.0` security models, and repository modules.";

const FRONTEND_LAYER_BLURB =
  "Single-page **React** application powered by `Vite`, Neobrutalist design tokens, i18n localization, and **TanStack Query** state management.";

const BACKEND_LAYER_BLURB =
  "Modular **Django REST Framework** service providing `JWT` authentication, Domain Audit Ledger, Celery worker orchestration, and OpenAPI docs.";

const ASYNC_LAYER_BLURB =
  "**PostgreSQL** relational datastore paired with `Redis` for Celery background worker queues and `Django Channels` WebSocket event broadcasts.";

function WorkerMarkdownBlock({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  const { html } = useMarkdownWorker(content);
  return (
    <div className={className} dangerouslySetInnerHTML={{ __html: html }} />
  );
}

export function FullStackDocsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<string>("all");

  const filteredFeatures = REPO_FEATURES.filter((item) => {
    const matchesSearch =
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.technologies.some((t) =>
        t.toLowerCase().includes(searchQuery.toLowerCase()),
      );

    const matchesCategory =
      activeCategory === "all" || item.category === activeCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="max-w-5xl mx-auto px-4 pt-28 pb-16 space-y-10 font-sans">
      {/* Neobrutalist Hero Banner */}
      <section className="rounded-[2.5rem] border-4 border-black bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-400 p-8 sm:p-10 shadow-card relative overflow-hidden text-white">
        <div className="absolute -right-10 -bottom-10 text-[12rem] opacity-10 select-none pointer-events-none">
          📖
        </div>
        <div className="relative z-10 space-y-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-black text-xs bg-white/90 text-black px-4 py-2 rounded-full border-2 border-black inline-block shadow-card-sm">
              Full-Stack Architecture & Feature Directory 📖
            </span>
            <span className="font-black text-xs bg-amber-300 text-black px-3 py-1.5 rounded-full border-2 border-black shadow-card-sm flex items-center gap-1">
              <Zap className="w-3.5 h-3.5 fill-black" /> Production Ready
            </span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-black text-white drop-shadow-[2px_2px_0_rgba(0,0,0,0.3)] tracking-tight">
            Open-Source Atelier Master Docs
          </h1>

          <WorkerMarkdownBlock
            content={HERO_INTRO_MARKDOWN}
            className="text-white/90 font-bold text-base sm:text-lg max-w-2xl leading-relaxed"
          />

          <div className="pt-2 flex items-center gap-4 flex-wrap">
            <div className="bg-white/95 text-black px-5 py-3 rounded-2xl border-2 border-black shadow-card-sm flex items-center gap-3">
              <div className="bg-indigo-500 text-white p-2 rounded-xl border border-black font-black text-sm">
                30+
              </div>
              <div className="text-left">
                <p className="text-xs font-black uppercase tracking-wider text-gray-500">
                  Modules
                </p>
                <p className="text-sm font-black text-gray-900">
                  Full-Stack Features
                </p>
              </div>
            </div>

            <div className="bg-white/95 text-black px-5 py-3 rounded-2xl border-2 border-black shadow-card-sm flex items-center gap-3">
              <div className="bg-emerald-400 text-black p-2 rounded-xl border border-black font-black text-sm">
                100%
              </div>
              <div className="text-left">
                <p className="text-xs font-black uppercase tracking-wider text-gray-500">
                  Coverage
                </p>
                <p className="text-sm font-black text-gray-900">
                  API Specifications
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* System Architecture Overview Grid */}
      <section className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-6 sm:p-8 shadow-card space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-4 border-black dark:border-[#2e2924] pb-4">
          <div className="flex items-center gap-3">
            <div className="bg-indigo-100 dark:bg-indigo-900/30 p-3 rounded-2xl border-2 border-black flex-shrink-0">
              <Layers className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <h2 className="text-2xl font-black dark:text-[#f0ebe2]">
                System Architecture Overview
              </h2>
              <p className="text-xs font-bold text-gray-500 dark:text-[#c4bbae]">
                Modular 3-Tier Stack: Frontend SPA, Django REST API, Async
                Queues
              </p>
            </div>
          </div>
          <span className="font-black text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 border-2 border-black px-3 py-1.5 rounded-xl shadow-card-sm shrink-0">
            Interactive Map
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Frontend Layer */}
          <div className="rounded-2xl border-4 border-black bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-[#1a1f2e] dark:to-[#151928] dark:border-[#2e2924] p-5 shadow-card hover:-translate-y-1 transition-transform flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b-2 border-black dark:border-[#2e2924] pb-2">
                <span className="font-black text-sm dark:text-[#f0ebe2] flex items-center gap-2">
                  <Globe className="w-4 h-4 text-blue-600 dark:text-blue-400" />{" "}
                  Frontend App Layer
                </span>
                <span className="text-[10px] font-black uppercase bg-blue-400 text-black px-2 py-0.5 rounded-full border border-black shadow-card-sm">
                  Vite + React
                </span>
              </div>
              <WorkerMarkdownBlock
                content={FRONTEND_LAYER_BLURB}
                className="text-xs font-bold text-gray-600 dark:text-[#c4bbae] leading-relaxed"
              />
            </div>
            <div className="flex flex-wrap gap-1.5 pt-2">
              <span className="px-2.5 py-1 bg-white dark:bg-[#25211c] text-black dark:text-[#f0ebe2] rounded-lg border-2 border-black text-[11px] font-extrabold">
                React 19
              </span>
              <span className="px-2.5 py-1 bg-white dark:bg-[#25211c] text-black dark:text-[#f0ebe2] rounded-lg border-2 border-black text-[11px] font-extrabold">
                Lucide Icons
              </span>
              <span className="px-2.5 py-1 bg-white dark:bg-[#25211c] text-black dark:text-[#f0ebe2] rounded-lg border-2 border-black text-[11px] font-extrabold">
                Monaco Editor
              </span>
            </div>
          </div>

          {/* Backend API Layer */}
          <div className="rounded-2xl border-4 border-black bg-gradient-to-br from-purple-50 to-pink-50 dark:from-[#281b2e] dark:to-[#1e1424] dark:border-[#2e2924] p-5 shadow-card hover:-translate-y-1 transition-transform flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b-2 border-black dark:border-[#2e2924] pb-2">
                <span className="font-black text-sm dark:text-[#f0ebe2] flex items-center gap-2">
                  <Server className="w-4 h-4 text-purple-600 dark:text-purple-400" />{" "}
                  Django REST Backend
                </span>
                <span className="text-[10px] font-black uppercase bg-purple-400 text-black px-2 py-0.5 rounded-full border border-black shadow-card-sm">
                  Python 3.11
                </span>
              </div>
              <WorkerMarkdownBlock
                content={BACKEND_LAYER_BLURB}
                className="text-xs font-bold text-gray-600 dark:text-[#c4bbae] leading-relaxed"
              />
            </div>
            <div className="flex flex-wrap gap-1.5 pt-2">
              <span className="px-2.5 py-1 bg-white dark:bg-[#25211c] text-black dark:text-[#f0ebe2] rounded-lg border-2 border-black text-[11px] font-extrabold">
                SimpleJWT
              </span>
              <span className="px-2.5 py-1 bg-white dark:bg-[#25211c] text-black dark:text-[#f0ebe2] rounded-lg border-2 border-black text-[11px] font-extrabold">
                Audit Engine
              </span>
              <span className="px-2.5 py-1 bg-white dark:bg-[#25211c] text-black dark:text-[#f0ebe2] rounded-lg border-2 border-black text-[11px] font-extrabold">
                OAuth 2.0 PKCE
              </span>
            </div>
          </div>

          {/* Database & Async Workers */}
          <div className="rounded-2xl border-4 border-black bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-[#162722] dark:to-[#0f1f1b] dark:border-[#2e2924] p-5 shadow-card hover:-translate-y-1 transition-transform flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b-2 border-black dark:border-[#2e2924] pb-2">
                <span className="font-black text-sm dark:text-[#f0ebe2] flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />{" "}
                  Async & Database
                </span>
                <span className="text-[10px] font-black uppercase bg-emerald-400 text-black px-2 py-0.5 rounded-full border border-black shadow-card-sm">
                  Celery + Redis
                </span>
              </div>
              <WorkerMarkdownBlock
                content={ASYNC_LAYER_BLURB}
                className="text-xs font-bold text-gray-600 dark:text-[#c4bbae] leading-relaxed"
              />
            </div>
            <div className="flex flex-wrap gap-1.5 pt-2">
              <span className="px-2.5 py-1 bg-white dark:bg-[#25211c] text-black dark:text-[#f0ebe2] rounded-lg border-2 border-black text-[11px] font-extrabold">
                Redis Broker
              </span>
              <span className="px-2.5 py-1 bg-white dark:bg-[#25211c] text-black dark:text-[#f0ebe2] rounded-lg border-2 border-black text-[11px] font-extrabold">
                WebSockets
              </span>
              <span className="px-2.5 py-1 bg-white dark:bg-[#25211c] text-black dark:text-[#f0ebe2] rounded-lg border-2 border-black text-[11px] font-extrabold">
                Async Tasks
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Feature & Module Directory Section */}
      <section className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="bg-amber-100 dark:bg-amber-900/30 p-3 rounded-2xl border-2 border-black flex-shrink-0">
              <Code className="w-6 h-6 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <h2 className="text-2xl font-black dark:text-[#f0ebe2]">
                Repository Feature Directory
              </h2>
              <p className="text-xs font-bold text-gray-500 dark:text-[#c4bbae]">
                Explore every feature, service worker, and module built into
                this repository.
              </p>
            </div>
          </div>

          {/* Search & Category Filter Pills */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 sm:w-64">
              <Search className="w-4 h-4 absolute left-3.5 top-3.5 text-gray-500" />
              <input
                type="text"
                placeholder="Search modules or tech..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] rounded-2xl text-sm font-bold dark:text-[#f0ebe2] placeholder-gray-400 shadow-card-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center gap-1.5 flex-wrap">
              {["all", "frontend", "security", "async", "realtime"].map(
                (cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={`px-3.5 py-2 rounded-full border-2 border-black text-xs font-black uppercase tracking-wider transition-all shadow-card-sm ${
                      activeCategory === cat
                        ? "bg-black text-white dark:bg-white dark:text-black"
                        : "bg-white text-black dark:bg-[#1f1c18] dark:text-[#c4bbae] dark:border-[#2e2924] hover:bg-gray-100 dark:hover:bg-[#25211c]"
                    }`}
                  >
                    {cat}
                  </button>
                ),
              )}
            </div>
          </div>
        </div>

        {/* Feature Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredFeatures.map((feat, idx) => (
            <div
              key={idx}
              className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-6 shadow-card hover:-translate-y-1 transition-transform flex flex-col justify-between space-y-5"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xl font-black dark:text-[#f0ebe2]">
                    {feat.name}
                  </h3>
                  <span className="font-black text-[10px] uppercase bg-amber-300 text-black px-3 py-1 rounded-full border-2 border-black shadow-card-sm shrink-0">
                    {feat.category}
                  </span>
                </div>

                <p className="text-xs font-bold text-gray-600 dark:text-[#c4bbae] leading-relaxed">
                  {feat.description}
                </p>

                <div className="flex flex-wrap gap-2 pt-1">
                  {feat.features.map((item, fIdx) => (
                    <span
                      key={fIdx}
                      className="text-[11px] font-extrabold px-3 py-1 bg-green-50 dark:bg-[#162722] text-green-900 dark:text-green-200 rounded-xl border-2 border-black flex items-center gap-1.5 shadow-card-sm"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-600 dark:text-green-400 shrink-0" />{" "}
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t-2 border-black dark:border-[#2e2924] flex items-center justify-between gap-4">
                <div className="flex flex-wrap gap-1.5">
                  {feat.technologies.map((t, tIdx) => (
                    <span
                      key={tIdx}
                      className="bg-indigo-50 dark:bg-indigo-900/30 text-indigo-900 dark:text-indigo-200 px-2.5 py-0.5 rounded-md border border-black font-mono text-[10px] font-black"
                    >
                      {t}
                    </span>
                  ))}
                </div>

                <Link
                  to={feat.endpointOrPath}
                  className={`inline-flex items-center gap-1.5 rounded-full bg-black text-white px-4 py-2 font-black text-xs border-2 border-black hover:bg-gray-800 transition-colors dark:bg-white dark:text-black dark:hover:bg-gray-200 shrink-0 ${CARD_FOCUS_RING}`}
                >
                  Open <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Interactive REST API Catalog */}
      <section className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-6 sm:p-8 shadow-card space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b-4 border-black dark:border-[#2e2924] pb-4">
          <div className="flex items-center gap-3">
            <div className="bg-emerald-100 dark:bg-emerald-900/30 p-3 rounded-2xl border-2 border-black flex-shrink-0">
              <Terminal className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <h2 className="text-2xl font-black dark:text-[#f0ebe2]">
                Core REST & OpenAPI Catalog
              </h2>
              <p className="text-xs font-bold text-gray-500 dark:text-[#c4bbae]">
                Principal Django REST Framework API endpoints available in the
                backend.
              </p>
            </div>
          </div>

          <a
            href="/api/docs/"
            target="_blank"
            rel="noopener noreferrer"
            className={`inline-flex items-center gap-2 rounded-full bg-emerald-400 text-black px-5 py-2.5 font-black text-xs border-2 border-black shadow-card-sm hover:bg-emerald-300 transition-colors shrink-0 ${CARD_FOCUS_RING}`}
          >
            Swagger UI Specs <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

        <div className="rounded-2xl border-4 border-black overflow-hidden bg-white dark:bg-[#151411] shadow-card-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="bg-gray-100 dark:bg-[#25211c] text-gray-900 dark:text-[#f0ebe2] border-b-4 border-black text-xs font-black uppercase tracking-wider">
                  <th className="py-3.5 px-4 w-24">Method</th>
                  <th className="py-3.5 px-4">Endpoint Path</th>
                  <th className="py-3.5 px-4">Description & Contract</th>
                </tr>
              </thead>
              <tbody className="divide-y-2 divide-black dark:divide-[#2e2924]">
                {API_ENDPOINTS.map((api, idx) => (
                  <tr
                    key={idx}
                    className="hover:bg-amber-50/50 dark:hover:bg-[#25211c]/50 transition-colors"
                  >
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2.5 py-1 text-[10px] font-black uppercase rounded-lg border-2 border-black shadow-card-sm ${
                          api.method === "GET"
                            ? "bg-emerald-400 text-black"
                            : "bg-indigo-400 text-black"
                        }`}
                      >
                        {api.method}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-black text-gray-900 dark:text-[#f0ebe2] text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-mono">{api.path}</span>
                        <CopyButton
                          text={`${api.method} ${api.path}`}
                          label="Copy"
                          copiedLabel="Copied!"
                        />
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-sans font-bold text-gray-600 dark:text-[#c4bbae]">
                      {api.desc}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FAQ Accordion Section */}
      <section>
        <FAQAccordion />
      </section>
    </div>
  );
}

export default FullStackDocsPage;
