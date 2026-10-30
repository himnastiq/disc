import React from 'react';

export function AppFooter() {
  return (
    <footer className="w-full border-t border-zinc-200 bg-white py-6 dark:border-zinc-800 dark:bg-zinc-950 text-xs text-zinc-500 dark:text-zinc-400">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-zinc-700 dark:text-zinc-300">
              Discovery Engine
            </span>
            <span>—</span>
            <span>Adaptive Cross-Domain Recommendation System</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <a
              href="https://github.com/recommenders-team/recommenders"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-zinc-900 dark:hover:text-zinc-100 underline underline-offset-4"
            >
              Microsoft Recommenders
            </a>
            <a
              href="https://grouplens.org/datasets/movielens/1m/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-zinc-900 dark:hover:text-zinc-100 underline underline-offset-4"
            >
              MovieLens 1M
            </a>
            <a
              href="https://cseweb.ucsd.edu/~jmcauley/datasets.html"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-zinc-900 dark:hover:text-zinc-100 underline underline-offset-4"
            >
              Amazon Product Reviews
            </a>
            <a
              href="https://msnews.github.io/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-zinc-900 dark:hover:text-zinc-100 underline underline-offset-4"
            >
              MIND Dataset
            </a>
          </div>
        </div>

        <div className="border-t border-zinc-100 dark:border-zinc-900 pt-3 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] text-zinc-400">
          <p>
            Developed strictly for non-commercial research, education, and benchmark evaluation.
          </p>
          <p>
            Zero user tracking or proprietary telemetry.
          </p>
        </div>
      </div>
    </footer>
  );
}

