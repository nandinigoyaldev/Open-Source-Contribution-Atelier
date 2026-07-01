import React, { useState } from "react";
import { Quote } from "lucide-react";

const QUOTES = [
  {
    text: "Programs must be written for people to read, and only incidentally for machines to execute.",
    author: "Harold Abelson",
  },
  {
    text: "Any fool can write code that a computer can understand. Good programmers write code that humans can understand.",
    author: "Martin Fowler",
  },
  {
    text: "First, solve the problem. Then, write the code.",
    author: "John Johnson",
  },
  {
    text: "Experience is the name everyone gives to their mistakes.",
    author: "Oscar Wilde",
  },
  {
    text: "Code is like humor. When you have to explain it, it’s bad.",
    author: "Cory House",
  },
  { text: "Make it work, make it right, make it fast.", author: "Kent Beck" },
  {
    text: "Sometimes it pays to stay in bed on Monday, rather than spending the rest of the week debugging Monday's code.",
    author: "Dan Salomon",
  },
  {
    text: "Perfection is achieved not when there is nothing more to add, but rather when there is nothing more to take away.",
    author: "Antoine de Saint-Exupery",
  },
  { text: "Simplicity is the soul of efficiency.", author: "Austin Freeman" },
  {
    text: "Before software can be reusable it first has to be usable.",
    author: "Ralph Johnson",
  },
];

function getDailyQuote() {
  const daysSinceEpoch = Math.floor(Date.now() / (1000 * 60 * 60 * 24));
  return QUOTES[daysSinceEpoch % QUOTES.length];
}

export function DailyQuoteWidget() {
  const [dailyQuote] = useState(getDailyQuote);

  return (
    <div className="rounded-2xl border-4 border-black bg-[#ffcc00] p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex flex-col justify-between hover:-translate-y-1 transition-transform">
      <div className="flex items-center gap-3 mb-4">
        <div className="bg-white p-2 rounded-xl border-2 border-black dark:bg-[#151411] dark:border-[#2e2924]">
          <Quote className="w-5 h-5 text-black dark:text-[#f0ebe2] fill-current" />
        </div>
        <h4 className="font-mono text-xs text-black uppercase tracking-wider font-black dark:text-[#c4bbae]">
          Quote of the Day
        </h4>
      </div>
      <blockquote className="space-y-3 mt-2">
        <p className="font-bold text-sm text-black leading-relaxed italic dark:text-[#f0ebe2]">
          "{dailyQuote.text}"
        </p>
        <footer className="font-black text-xs text-black/70 dark:text-[#c4bbae]">
          — {dailyQuote.author}
        </footer>
      </blockquote>
    </div>
  );
}
