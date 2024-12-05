import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthState } from 'react-firebase-hooks/auth';
import { auth } from './firebase';
import { 
  Github, 
  Plus, 
  Moon, 
  Sun, 
  Search, 
  Code, 
  FileCode, 
  MessagesSquare, 
  Trash2, 
  ExternalLink,
  Loader2 
} from 'lucide-react';

// Import components
import { Dashboard as ChatSidebar } from './components/Dashboard';
import { ChatWindow } from './components/ChatWindow';
import { NewChatModal } from './components/NewChatModal';
import { SearchModal } from './components/SearchModal';
import { CodePreview } from './components/CodePreview';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';

// Import types and utils
import { ChatState, Chat } from './types';
import { generateId } from './utils';

// Constants
const STORAGE_KEY = 'github-repo-chat-data';
const THEME_KEY = 'github-repo-chat-theme';

interface ExtendedChatState extends ChatState {
  files: string[];
}

function GitHubRepoChat() {
  const [state, setState] = useState<ExtendedChatState>(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : {
      chats: [],
      currentChatId: null,
      isLoading: false,
      error: null,
      files: [],
    };
  });
  
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem(THEME_KEY);
    return saved ? JSON.parse(saved) : window.matchMedia('(prefers-color-scheme: dark)').matches;
  });
  
  const [isNewChatModalOpen, setIsNewChatModalOpen] = useState(false);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [showCodePreview, setShowCodePreview] = useState(true);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  useEffect(() => {
    localStorage.setItem(THEME_KEY, JSON.stringify(isDarkMode));
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  const currentChat = state.currentChatId 
    ? state.chats.find(chat => chat.id === state.currentChatId)
    : null;

  const handleCreateChat = async (repoUrl: string, token?: string) => {
    try {
      const urlPattern = /^https?:\/\/github\.com\/[\w-]+\/[\w.-]+(?:\/)?(?:\.git)?$/;
      if (!urlPattern.test(repoUrl)) {
        throw new Error('Invalid GitHub repository URL. Please use the format: https://github.com/owner/repo');
      }

      const cleanUrl = repoUrl.replace(/\.git$/, '').replace(/\/$/, '');
      setState(prev => ({ ...prev, isLoading: true, error: null }));
      const chatId = generateId();

      const response = await fetch('http://localhost:5000/load-repo', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` })
        },
        body: JSON.stringify({ 
          repo_url: cleanUrl,
          chat_id: chatId 
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || 'Failed to load repository');
      }

      const fileList = await fetch('http://localhost:5000/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId }),
      }).then(res => res.json()).then(data => data.files);

      const newChat: Chat = {
        id: chatId,
        repoUrl: cleanUrl,
        title: cleanUrl.split('/').pop() || 'New Chat',
        messages: [{
          role: 'assistant',
          content: 'Repository loaded successfully! How can I help you with this code?',
          timestamp: new Date(),
        }],
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      setState(prev => ({
        ...prev,
        chats: [...prev.chats, newChat],
        currentChatId: newChat.id,
        isLoading: false,
        files: fileList,
      }));
      setIsNewChatModalOpen(false);
    } catch (error) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'An error occurred',
      }));
    }
  };

  const handleDeleteChat = (chatId: string) => {
    setState(prev => ({
      ...prev,
      chats: prev.chats.filter(chat => chat.id !== chatId),
      currentChatId: prev.currentChatId === chatId ? null : prev.currentChatId,
      files: prev.currentChatId === chatId ? [] : prev.files,
    }));
  };

  const handleSelectChat = async (chatId: string) => {
    try {
      setState(prev => ({ ...prev, isLoading: true }));
      
      const fileList = await fetch('http://localhost:5000/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId }),
      }).then(res => res.json()).then(data => data.files);

      setState(prev => ({ 
        ...prev, 
        currentChatId: chatId,
        files: fileList,
        isLoading: false 
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'An error occurred',
      }));
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!currentChat) return;
    try {
      setState(prev => ({ ...prev, isLoading: true, error: null }));
      const updatedChat: Chat = {
        ...currentChat,
        messages: [
          ...currentChat.messages,
          { role: 'user', content, timestamp: new Date() },
        ],
        updatedAt: new Date(),
      };
      setState(prev => ({
        ...prev,
        chats: prev.chats.map(chat => 
          chat.id === currentChat.id ? updatedChat : chat
        ),
      }));
      const response = await fetch('http://localhost:5000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: content,
          chat_id: currentChat.id,
          conversation_history: currentChat.messages
            .map(m => `${m.role === 'user' ? 'User: ' : 'Assistant: '}${m.content}`)
            .join('\n'),
        }),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || 'Failed to get response');
      }
      
      const data = await response.json();
      
      setState(prev => ({
        ...prev,
        chats: prev.chats.map(chat => 
          chat.id === currentChat.id ? {
            ...chat,
            messages: [
              ...chat.messages,
              { role: 'assistant', content: data.response, timestamp: new Date() },
            ],
            updatedAt: new Date(),
          } : chat
        ),
        isLoading: false,
      }));
      // Update files list if new files were created
      const fileList = await fetch('http://localhost:5000/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: currentChat.id }),
      }).then(res => res.json()).then(data => data.files);
      setState(prev => ({
        ...prev,
        files: fileList
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'An error occurred',
      }));
    }
  };

  return (
    <div className={`h-screen flex flex-col bg-gray-50 dark:bg-gray-900 transition-colors duration-200`}>
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Github className="w-8 h-8 text-primary-600 dark:text-primary-400" />
              <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
                 RepoChat
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowCodePreview(!showCodePreview)}
                className="p-2 text-gray-500 hover:text-primary-600 dark:text-gray-400 dark:hover:text-primary-400 transition-colors"
                title="Toggle code preview"
              >
                <Code className="w-5 h-5" />
              </button>
              <button
                onClick={() => setIsSearchModalOpen(true)}
                className="p-2 text-gray-500 hover:text-primary-600 dark:text-gray-400 dark:hover:text-primary-400 transition-colors"
                title="Search messages"
              >
                <Search className="w-5 h-5" />
              </button>
              <button
                onClick={() => setIsDarkMode(!isDarkMode)}
                className="p-2 text-gray-500 hover:text-primary-600 dark:text-gray-400 dark:hover:text-primary-400 transition-colors"
                title="Toggle theme"
              >
                {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
              <button
                onClick={() => setIsNewChatModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                <Plus className="w-5 h-5" />
                New Chat
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        <ChatSidebar
          chats={state.chats}
          currentChatId={state.currentChatId}
          onSelectChat={handleSelectChat}
          onDeleteChat={handleDeleteChat}
        />
        
        <div className="flex-1 flex min-w-0">
          {currentChat ? (
            <>
              <ChatWindow
                chat={currentChat}
                isLoading={state.isLoading}
                error={state.error}
                onSendMessage={handleSendMessage}
                onFileOperation={async (operation) => {
                  try {
                    const response = await fetch('http://localhost:5000/save-file', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        chat_id: currentChat.id,
                        path: operation.path,
                        content: operation.content,
                        type: operation.type
                      }),
                    });
                    if (!response.ok) {
                      throw new Error('Failed to save file');
                    }
                    // Update files list
                    const fileList = await fetch('http://localhost:5000/files', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ chat_id: currentChat.id }),
                    }).then(res => res.json()).then(data => data.files);
                    setState(prev => ({
                      ...prev,
                      files: fileList
                    }));
                  } catch (error) {
                    console.error('Error saving file:', error);
                    setState(prev => ({
                      ...prev,
                      error: 'Failed to save file changes'
                    }));
                  }
                }}
                className={showCodePreview ? 'w-1/2' : 'w-full'}
                files={state.files}
              />
              {showCodePreview && (
                <CodePreview
                  repoUrl={currentChat.repoUrl}
                  className="w-1/2 border-l border-gray-200 dark:border-gray-700"
                />
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center p-8">
              <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 text-center">
                <FileCode className="w-16 h-16 mx-auto mb-4 text-primary-600 dark:text-primary-400" />
                <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  Welcome to GitHub Repository Chat
                </h2>
                <p className="text-gray-500 dark:text-gray-400 mb-6">
                  Select an existing chat or create a new one to start exploring repositories with AI assistance.
                </p>
                <button
                  onClick={() => setIsNewChatModalOpen(true)}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
                >
                  <Plus className="w-5 h-5" />
                  New Chat
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      <NewChatModal
        isOpen={isNewChatModalOpen}
        onClose={() => setIsNewChatModalOpen(false)}
        onSubmit={handleCreateChat}
        isLoading={state.isLoading}
      />

      <SearchModal
        isOpen={isSearchModalOpen}
        onClose={() => setIsSearchModalOpen(false)}
        chats={state.chats}
        onSelectChat={handleSelectChat}
      />
    </div>
  );
}

function App() {
  const [user, loading] = useAuthState(auth);

  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route
          path="/login"
          element={user ? <Navigate to="/chat" /> : <LoginPage />}
        />
        <Route
          path="/chat/*"
          element={user ? <GitHubRepoChat /> : <Navigate to="/login" />}
        />
      </Routes>
    </Router>
  );
}

export default App;