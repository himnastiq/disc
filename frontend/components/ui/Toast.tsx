'use client';

import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface ToastProps {
  type?: 'success' | 'error' | 'info';
  title: string;
  description?: string;
  onClose?: () => void;
  className?: string;
}

export function Toast({
  type = 'info',
  title,
  description,
  onClose,
  className,
}: ToastProps) {
  const icons = {
    success: <CheckCircle2 className="h-5 w-5 text-emerald-500" />,
    error: <AlertCircle className="h-5 w-5 text-red-500" />,
    info: <Info className="h-5 w-5 text-sky-500" />,
  };

  return (
    <div
      role="status"
      className={twMerge(
        clsx(
          'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-lg dark:border-zinc-800 dark:bg-zinc-900',
          className
        )
      )}
    >
      <div className="shrink-0">{icons[type]}</div>
      <div className="flex-1">
        <h5 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{title}</h5>
        {description && (
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{description}</p>
        )}
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="shrink-0 rounded p-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
          aria-label="Close notification"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

