'use client';

import React, { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { Sun, Moon, Laptop } from 'lucide-react';
import { Button } from './Button';

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <Button variant="ghost" size="sm" className="w-9 px-0" aria-label="Toggle theme">
        <Sun className="h-4 w-4 text-zinc-400" />
      </Button>
    );
  }

  const cycleTheme = () => {
    if (theme === 'system') setTheme('light');
    else if (theme === 'light') setTheme('dark');
    else setTheme('system');
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={cycleTheme}
      className="w-9 px-0"
      aria-label={`Current theme: ${theme}. Click to switch theme.`}
    >
      {theme === 'dark' ? (
        <Moon className="h-4 w-4 text-zinc-200" />
      ) : theme === 'light' ? (
        <Sun className="h-4 w-4 text-amber-500" />
      ) : (
        <Laptop className="h-4 w-4 text-zinc-400" />
      )}
    </Button>
  );
}
