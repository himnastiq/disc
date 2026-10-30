import React from 'react';

export function AppFooter() {
  return (
    <footer className="w-full border-t border-[var(--color-border)] bg-[var(--color-bg)] py-6 text-xs text-[var(--color-text-muted)]">
      <div className="max-w-[52rem] mx-auto px-4 sm:px-6 space-y-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-[var(--color-text-secondary)]">
              Discovery Engine
            </span>
            <span>·</span>
            <span className="text-[var(--color-text-muted)]">Adaptive Multi-Domain Recommendations</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--color-text-secondary)]">
            <a
              href="https://github.com/recommenders-team/recommenders"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[var(--color-text)] underline underline-offset-4"
            >
              Recommenders (MIT)
            </a>
            <a
              href="https://grouplens.org/datasets/movielens/1m/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[var(--color-text)] underline underline-offset-4"
            >
              MovieLens
            </a>
            <a
              href="https://cseweb.ucsd.edu/~jmcauley/datasets.html"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[var(--color-text)] underline underline-offset-4"
            >
              Amazon Reviews
            </a>
            <a
              href="https://msnews.github.io/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[var(--color-text)] underline underline-offset-4"
            >
              MIND
            </a>
          </div>
        </div>

        <div className="border-t border-[var(--color-border)] pt-3 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] text-[var(--color-text-muted)]">
          <p>
            Developed strictly for non-commercial education, college showcase, and evaluation.
          </p>
          <p>
            Zero fabricated results · Strict temporal evaluation
          </p>
        </div>
      </div>
    </footer>
  );
}
