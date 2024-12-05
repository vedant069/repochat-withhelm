import React, { useState, useRef, useEffect } from 'react';
import { Send, File, X } from 'lucide-react';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  disabled: boolean;
  files?: string[];
  activeFile?: string;
  onClearActiveFile?: () => void;
}

export function ChatInput({ 
  onSendMessage, 
  disabled, 
  files = [], 
  activeFile,
  onClearActiveFile 
}: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredFiles, setFilteredFiles] = useState<string[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const atIndex = message.lastIndexOf('@');
    if (atIndex !== -1) {
      const query = message.slice(atIndex + 1).toLowerCase();
      const filtered = files.filter(file => 
        file.toLowerCase().includes(query)
      );
      setFilteredFiles(filtered);
      setShowSuggestions(filtered.length > 0);
      setSelectedIndex(0);
    } else {
      setShowSuggestions(false);
    }
  }, [message, files]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (suggestionsRef.current && !suggestionsRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (showSuggestions) {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(prev => (prev + 1) % filteredFiles.length);
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(prev => (prev - 1 + filteredFiles.length) % filteredFiles.length);
          break;
        case 'Enter':
          if (filteredFiles.length > 0) {
            e.preventDefault();
            const atIndex = message.lastIndexOf('@');
            const newMessage = message.slice(0, atIndex) + '@' + filteredFiles[selectedIndex];
            setMessage(newMessage);
            setShowSuggestions(false);
          }
          break;
        case 'Escape':
          setShowSuggestions(false);
          break;
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
      // If no @ in message and there's an active file, prepend it
      const finalMessage = !message.includes('@') && activeFile
        ? `@${activeFile} ${message}`
        : message;
      
      onSendMessage(finalMessage);
      setMessage('');
      setShowSuggestions(false);
    }
  };

  const handleSuggestionClick = (file: string) => {
    const atIndex = message.lastIndexOf('@');
    const newMessage = message.slice(0, atIndex) + '@' + file;
    setMessage(newMessage);
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  return (
    <div className="relative flex flex-col gap-2">
      {/* Active File Context Banner */}
      {activeFile && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-lg text-sm">
          <File className="w-4 h-4" />
          <span>Currently viewing: {activeFile}</span>
          <button
            onClick={onClearActiveFile}
            className="ml-auto p-1 hover:bg-blue-100 dark:hover:bg-blue-800 rounded-full"
            title="Clear file context"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* File Suggestions */}
      {showSuggestions && (
        <div
          ref={suggestionsRef}
          className="absolute bottom-full mb-2 w-full max-h-60 overflow-y-auto bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
        >
          {filteredFiles.map((file, index) => (
            <button
              key={file}
              className={`w-full px-4 py-2 text-left flex items-center gap-2 hover:bg-gray-100 dark:hover:bg-gray-700 ${
                index === selectedIndex ? 'bg-gray-100 dark:bg-gray-700' : ''
              }`}
              onClick={() => handleSuggestionClick(file)}
            >
              <File className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-900 dark:text-gray-100">{file}</span>
            </button>
          ))}
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={activeFile 
            ? `Ask about ${activeFile} or type @ to switch files...` 
            : "Type @ to select a file, or ask about specific functions..."}
          className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 dark:disabled:bg-gray-900 disabled:text-gray-500 dark:disabled:text-gray-400"
        />
        <button
          type="submit"
          disabled={disabled || !message.trim()}
          className="rounded-lg bg-blue-500 px-4 py-2 text-white hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          <Send className="w-5 h-5" />
        </button>
      </form>
    </div>
  );
}