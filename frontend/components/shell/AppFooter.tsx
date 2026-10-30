import React from 'react';

export function AppFooter() {
  return (
    <footer className="w-full border-t border-[var(--color-border)] bg-[var(--color-bg)] py-6 text-center text-xs text-[var(--color-text-muted)]">
      <div className="max-w-[52rem] mx-auto px-4 sm:px-6">
        <p>Made with Next + FastAPI</p>
      </div>
    </footer>
  );
}
