import React, { useState, useMemo } from 'react';
import { X, Search, MessageSquare } from 'lucide-react';
import { Chat, Message } from '../types';

interface SearchResult {
  chatId: string;
  chatTitle: string;
  message: Message;
}

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  chats: Chat[];
  onSelectChat: (chatId: string) => void;
}

export function SearchModal({ isOpen, onClose, chats, onSelectChat }: SearchModalProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];

    const query = searchQuery.toLowerCase();
    const results: SearchResult[] = [];

    chats.forEach(chat => {
      chat.messages.forEach(message => {
        if (message.content.toLowerCase().includes(query)) {
          results.push({
            chatId: chat.id,
            chatTitle: chat.title,
            message,
          });
        }
      });
    });

    return results;
  }, [searchQuery, chats]);

  if (!isOpen) return null;

  const handleSelectResult = (chatId: string) => {
    onSelectChat(chatId);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-start justify-center p-4 pt-[10vh]">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-2xl w-full">
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Search Messages</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search in messages..."
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 pl-10 pr-4 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400"
            />
          </div>
        </div>

        <div className="max-h-[60vh] overflow-y-auto">
          {searchResults.length === 0 && searchQuery.trim() !== '' ? (
            <div className="p-4 text-center text-gray-500 dark:text-gray-400">
              No messages found
            </div>
          ) : (
            <div className="divide-y dark:divide-gray-700">
              {searchResults.map((result, index) => (
                <div
                  key={index}
                  className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                  onClick={() => handleSelectResult(result.chatId)}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
                      <MessageSquare className="w-4 h-4 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                        {result.chatTitle}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {result.message.content.substring(0, 150)}
                        {result.message.content.length > 150 ? '...' : ''}
                      </p>
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                        {new Date(result.message.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}