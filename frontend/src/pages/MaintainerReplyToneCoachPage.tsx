import { Link } from "react-router-dom";
import { ArrowLeft, MessageSquareHeart } from "lucide-react";
import { MaintainerReplyToneCoach } from "../components/ui/MaintainerReplyToneCoach";

export function MaintainerReplyToneCoachPage() {
  return (
    <div className="container mx-auto max-w-5xl px-4 py-8">
      <div className="mb-8">
        <Link
          to="/bounties"
          className="mb-4 inline-flex items-center gap-2 text-xs font-black uppercase tracking-wide text-muted hover:text-primary dark:text-[#c4bbae]"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          Practice
        </Link>
        <p className="mb-2 inline-flex items-center gap-2 rounded-full border-2 border-black bg-rose-100 px-3 py-1 text-[10px] font-black uppercase tracking-wider dark:bg-rose-900/40 dark:border-[#2e2924]">
          <MessageSquareHeart className="h-3.5 w-3.5" aria-hidden />
          Module 4 · Etiquette
        </p>
        <h1 className="text-3xl font-black tracking-tight text-text dark:text-[#fff8ef]">
          Maintainer Reply Tone Coach
        </h1>
        <p className="mt-2 max-w-2xl text-sm font-bold text-muted dark:text-[#d7cec0]">
          Practice polite issue and PR comments before you hit send. Flags
          demanding tone, missing context, and “any update???” pings — then
          suggests a kinder rewrite.
        </p>
      </div>

      <MaintainerReplyToneCoach enableXp />
    </div>
  );
}
