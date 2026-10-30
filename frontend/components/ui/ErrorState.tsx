'use client';

import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './Button';
import { Card, CardContent } from './Card';

export interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'An unexpected error occurred while loading this section.',
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <Card className={className}>
      <CardContent className="flex flex-col items-center justify-center py-10 text-center">
        <div className="rounded-full bg-red-100 p-3 text-red-600 dark:bg-red-950/60 dark:text-red-400 mb-4">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <h4 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-1">
          {title}
        </h4>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mb-6">
          {message}
        </p>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry} className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Try Again
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

