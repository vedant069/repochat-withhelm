import React, { useState } from 'react';
import { Github } from 'lucide-react';

interface RepoInputProps {
  onSubmit: (url: string) => void;
  disabled: boolean;
}

export function RepoInput({ onSubmit, disabled }: RepoInputProps) {
  const [url, setUrl] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim() && !disabled) {
      onSubmit(url);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <div className="flex-1 relative">
        <Github className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={disabled}
          placeholder="Enter GitHub repository URL..."
          className="w-full rounded-lg border border-gray-300 pl-10 pr-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
        />
      </div>
      <button
        type="submit"
        disabled={disabled || !url.trim()}
        className="rounded-lg bg-blue-500 px-6 py-2 text-white hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        Load
      </button>
    </form>
  );
}