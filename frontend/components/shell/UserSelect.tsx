'use client';

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { User, Search, Check, ChevronDown, Sparkles } from 'lucide-react';
import { useUsers } from '@/lib/api/hooks';

export interface UserSelectProps {
  currentType: string;
  currentUser: string;
  onUserChange: (userId: string) => void;
}

export function UserSelect({ currentType, currentUser, onUserChange }: UserSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);

  const { data: usersResponse, isLoading } = useUsers(currentType);
  const users = useMemo(() => usersResponse?.users || [], [usersResponse?.users]);

  const activeUser = useMemo(() => {
    return users.find((u) => u.user_id === currentUser);
  }, [users, currentUser]);

  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users;
    const q = searchQuery.toLowerCase();
    return users.filter(
      (u) =>
        u.user_id.toLowerCase().includes(q) ||
        (u.persona && u.persona.toLowerCase().includes(q)) ||
        u.top_categories.some((c) => c.toLowerCase().includes(q))
    );
  }, [users, searchQuery]);

  const openDropdown = useCallback(() => {
    setSearchQuery('');
    setFocusedIndex(0);
    setIsOpen(true);
  }, []);

  const closeDropdown = useCallback(() => {
    setIsOpen(false);
  }, []);

  const toggleDropdown = useCallback(() => {
    if (isOpen) {
      closeDropdown();
    } else {
      openDropdown();
    }
  }, [isOpen, openDropdown, closeDropdown]);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === 'ArrowDown' || e.key === ' ') {
        e.preventDefault();
        openDropdown();
      }
      return;
    }

    if (e.key === 'Escape') {
      e.preventDefault();
      closeDropdown();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setFocusedIndex((prev) => (prev + 1 < filteredUsers.length ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setFocusedIndex((prev) => (prev - 1 >= 0 ? prev - 1 : filteredUsers.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const selected = filteredUsers[focusedIndex];
      if (selected) {
        onUserChange(selected.user_id);
        closeDropdown();
      }
    }
  };

  const demoUsers = useMemo(() => filteredUsers.filter((u) => u.is_demo), [filteredUsers]);
  const regularUsers = useMemo(() => filteredUsers.filter((u) => !u.is_demo), [filteredUsers]);

  return (
    <div className="relative" ref={containerRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={toggleDropdown}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={`User #${currentUser}${activeUser?.persona ? ` · ${activeUser.persona}` : ''}: Select user persona`}
        className="h-8 flex items-center gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 text-xs font-medium text-[var(--color-text)] transition-colors hover:bg-[var(--color-elevated)] cursor-pointer focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)]"
      >
        <User className="h-3.5 w-3.5 text-[var(--color-text-secondary)]" />
        <span className="font-semibold text-[var(--color-text)]">
          User #{currentUser}
        </span>
        {activeUser?.persona && (
          <span className="hidden sm:inline text-[var(--color-text-secondary)] font-normal truncate max-w-[140px]">
            · {activeUser.persona}
          </span>
        )}
        <ChevronDown className="h-3 w-3 text-[var(--color-text-muted)] ml-0.5" />
      </button>

      {/* Popover Dropdown */}
      {isOpen && (
        <div
          role="listbox"
          aria-label="Users list"
          className="absolute right-0 z-50 mt-1.5 w-72 sm:w-80 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-1.5 shadow-2xl"
        >
          {/* Search Input */}
          <div className="relative mb-2">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-[var(--color-text-muted)]" />
            <input
              autoFocus
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setFocusedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search user ID or persona..."
              className="w-full h-8.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-bg)] pl-8 pr-2.5 text-xs text-[var(--color-text)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent-text)]"
            />
          </div>

          {/* User Options List */}
          <div className="max-h-64 overflow-y-auto space-y-1">
            {filteredUsers.length === 0 ? (
              <div className="py-4 text-center text-xs text-[var(--color-text-muted)]">
                No users matching &quot;{searchQuery}&quot;
              </div>
            ) : (
              <>
                {/* Demo Users Section */}
                {demoUsers.length > 0 && (
                  <div>
                    <div className="px-2 py-1 text-[10px] font-semibold tracking-wider uppercase text-[var(--color-text-muted)] flex items-center gap-1">
                      <Sparkles className="h-3 w-3 text-[var(--color-accent)]" /> Demo Personas
                    </div>
                    {demoUsers.map((u) => {
                      const globalIndex = filteredUsers.findIndex((x) => x.user_id === u.user_id);
                      const isSelected = u.user_id === currentUser;
                      const isFocused = globalIndex === focusedIndex;

                      return (
                        <div
                          key={u.user_id}
                          role="option"
                          aria-selected={isSelected}
                          onClick={() => {
                            onUserChange(u.user_id);
                            closeDropdown();
                          }}
                          onMouseEnter={() => setFocusedIndex(globalIndex)}
                          className={`flex items-start justify-between rounded-[4px] px-2.5 py-1.5 text-xs cursor-pointer transition-colors ${
                            isFocused
                              ? 'bg-[var(--color-elevated)] text-[var(--color-text)]'
                              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                          }`}
                        >
                          <div className="min-w-0 pr-2">
                            <div className="font-semibold text-[var(--color-text)] flex items-center gap-1.5">
                              <span>User #{u.user_id}</span>
                              <span className="text-[10px] font-medium text-[var(--color-accent-text)] bg-[var(--color-accent)]/10 px-1 py-0.2 rounded">
                                Demo
                              </span>
                            </div>
                            {u.persona && (
                              <p className="text-[11px] text-[var(--color-text-secondary)] truncate">
                                {u.persona}
                              </p>
                            )}
                            <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                              {u.interaction_count} ratings · {u.top_categories.slice(0, 2).join(', ')}
                            </p>
                          </div>
                          {isSelected && (
                            <Check className="h-4 w-4 text-[var(--color-accent-text)] shrink-0 mt-0.5" />
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Regular Users Section */}
                {regularUsers.length > 0 && (
                  <div className={demoUsers.length > 0 ? 'mt-2 pt-1 border-t border-[var(--color-border)]' : ''}>
                    {demoUsers.length > 0 && (
                      <div className="px-2 py-1 text-[10px] font-semibold tracking-wider uppercase text-[var(--color-text-muted)]">
                        Sampled Users
                      </div>
                    )}
                    {regularUsers.map((u) => {
                      const globalIndex = filteredUsers.findIndex((x) => x.user_id === u.user_id);
                      const isSelected = u.user_id === currentUser;
                      const isFocused = globalIndex === focusedIndex;

                      return (
                        <div
                          key={u.user_id}
                          role="option"
                          aria-selected={isSelected}
                          onClick={() => {
                            onUserChange(u.user_id);
                            closeDropdown();
                          }}
                          onMouseEnter={() => setFocusedIndex(globalIndex)}
                          className={`flex items-center justify-between rounded-[4px] px-2.5 py-1.5 text-xs cursor-pointer transition-colors ${
                            isFocused
                              ? 'bg-[var(--color-elevated)] text-[var(--color-text)]'
                              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                          }`}
                        >
                          <div className="min-w-0 pr-2">
                            <span className="font-medium text-[var(--color-text)]">
                              User #{u.user_id}
                            </span>
                            {u.persona && (
                              <span className="text-[11px] text-[var(--color-text-muted)] ml-2">
                                ({u.persona})
                              </span>
                            )}
                          </div>
                          {isSelected && (
                            <Check className="h-4 w-4 text-[var(--color-accent-text)] shrink-0" />
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
