import React from 'react';
import { Inbox } from 'lucide-react';
import { Card, CardContent } from './Card';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title?: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon = <Inbox className="h-8 w-8 text-zinc-400" />,
  title = 'No items found',
  description = 'There is currently no data to display.',
  action,
  className,
}: EmptyStateProps) {
  return (
    <Card className={className}>
      <CardContent className="flex flex-col items-center justify-center py-12 text-center">
        <div className="rounded-full bg-zinc-100 p-4 dark:bg-zinc-800 mb-4">
          {icon}
        </div>
        <h4 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-1">
          {title}
        </h4>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mb-4">
          {description}
        </p>
        {action && <div>{action}</div>}
      </CardContent>
    </Card>
  );
}

