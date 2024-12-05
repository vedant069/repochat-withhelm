import React from 'react';
import { MessageSquare, Bot, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Message } from '../types';

interface ChatMessageProps {
  message: Message;
  isLatest?: boolean;
}

export function ChatMessage({ message, isLatest }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const timestamp = message.timestamp ? new Date(message.timestamp) : new Date();
  const isValidDate = timestamp instanceof Date && !isNaN(timestamp.getTime());

  return (
    <div
      className={`flex gap-6 ${isUser ? 'flex-row-reverse' : ''} mb-6 animate-fade-in opacity-0 [animation-fill-mode:forwards]`}
    >
      {/* Avatar */}
      <div className="flex flex-col items-center gap-2">
        <div
          className={`
            h-10 w-10 rounded-full flex items-center justify-center
            transition-transform duration-300 hover:scale-110
            ${isUser ? 'bg-gradient-to-br from-blue-500 to-blue-600' : 'bg-gradient-to-br from-gray-600 to-gray-700'}
            shadow-lg
          `}
        >
          {isUser ? (
            <MessageSquare className="w-5 h-5 text-white" />
          ) : (
            <Bot className="w-5 h-5 text-white" />
          )}
        </div>
        {isLatest && isUser && (
          <div className="text-xs text-gray-400 flex items-center gap-1">
            <Check className="w-3 h-3" />
            Sent
          </div>
        )}
      </div>

      {/* Message Content */}
      <div className={`flex-1 max-w-[70%] ${isUser ? 'text-right' : 'text-left'}`}>
        <div
          className={`
            inline-block rounded-2xl px-6 py-3
            shadow-md transition-all duration-300 hover:shadow-lg
            ${isUser 
              ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white' 
              : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100'
            }
          `}
        >
          <ReactMarkdown 
            className={`
              prose prose-sm max-w-none
              ${isUser 
                ? 'prose-invert' 
                : 'prose-gray dark:prose-invert'
              }
              prose-p:leading-relaxed
              prose-pre:bg-black/10 prose-pre:backdrop-blur-sm
              prose-code:text-blue-500 dark:prose-code:text-blue-400
              prose-a:text-blue-500 dark:prose-a:text-blue-400
              prose-strong:font-semibold
              prose-headings:font-semibold
            `}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Timestamp */}
        <div 
          className={`
            text-xs text-gray-400 mt-2 flex items-center gap-2
            ${isUser ? 'justify-end' : 'justify-start'}
          `}
        >
          {isValidDate && (
            <>
              <span>{timestamp.toLocaleDateString()}</span>
              <span>•</span>
              <span>{timestamp.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit'
              })}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}