import React, { useState } from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import { signOut } from 'firebase/auth';
import { auth } from '../firebase';
import { useAuthState } from 'react-firebase-hooks/auth';
import { Github, LogOut, Plus, Moon, Sun, Search, Code, MessagesSquare, User, Settings } from 'lucide-react';
import { ChatWindow } from '../components/ChatWindow2';
import { NewChatModal } from '../components/NewChatModal';
import { SearchModal } from '../components/SearchModal';
import { CodePreview } from '../components/CodePreview';
import { Chat } from '../types';

export default function Dashboard() {
  const [user] = useAuthState(auth);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    return saved ? JSON.parse(saved) : window.matchMedia('(prefers-color-scheme: dark)').matches;
  });
  const [isNewChatModalOpen, setIsNewChatModalOpen] = useState(false);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [currentChat, setCurrentChat] = useState<Chat | null>(null);
  const [showCodePreview, setShowCodePreview] = useState(true);

  const handleSignOut = () => {
    signOut(auth);
  };

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
    localStorage.setItem('theme', JSON.stringify(!isDarkMode));
    if (!isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* Header */}
      <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 sticky top-0 z-50 backdrop-blur-sm bg-white/80 dark:bg-slate-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
                <Github className="w-8 h-8 text-orange-600 dark:text-orange-400" />
                <span className="text-xl font-bold bg-gradient-to-r from-orange-600 to-purple-600 bg-clip-text text-transparent">RepoChat</span>
              </Link>
            </div>

            <div className="flex items-center gap-4">
              <button
                onClick={() => setShowCodePreview(!showCodePreview)}
                className="p-2.5 text-slate-600 hover:text-orange-600 dark:text-slate-300 dark:hover:text-orange-400 transition-colors rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"
                title="Toggle code preview"
              >
                <Code className="w-5 h-5" />
              </button>
              <button
                onClick={() => setIsSearchModalOpen(true)}
                className="p-2.5 text-slate-600 hover:text-orange-600 dark:text-slate-300 dark:hover:text-orange-400 transition-colors rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"
                title="Search chats"
              >
                <Search className="w-5 h-5" />
              </button>
              <button
                onClick={toggleTheme}
                className="p-2.5 text-slate-600 hover:text-orange-600 dark:text-slate-300 dark:hover:text-orange-400 transition-colors rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"
                title="Toggle theme"
              >
                {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
              <button
                onClick={() => setIsNewChatModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-600 to-purple-600 text-white rounded-lg hover:opacity-90 transition-opacity shadow-sm"
              >
                <Plus className="w-5 h-5" />
                New Chat
              </button>
              <div className="relative group">
                <button className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                  <img
                    src={user?.photoURL || 'https://ui-avatars.com/api/?name=User'}
                    alt={user?.displayName || 'User'}
                    className="w-8 h-8 rounded-full ring-2 ring-orange-600/20"
                  />
                </button>
                <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 hidden group-hover:block transform transition-all duration-200 ease-out origin-top-right">
                  <div className="p-4 border-b border-slate-200 dark:border-slate-700">
                    <p className="text-sm font-medium text-slate-900 dark:text-white">{user?.displayName}</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400 truncate">{user?.email}</p>
                  </div>
                  <div className="p-2">
                    <button
                      onClick={handleSignOut}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      Sign Out
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-8">
          {/* Sidebar */}
          <div className="w-72 flex-shrink-0">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
              <nav className="flex flex-col gap-1 p-3">
                <Link
                  to="/dashboard"
                  className="flex items-center gap-3 px-4 py-2.5 text-slate-700 dark:text-slate-200 hover:bg-orange-50 dark:hover:bg-orange-900/20 hover:text-orange-600 dark:hover:text-orange-400 rounded-lg transition-all duration-200"
                >
                  <MessagesSquare className="w-5 h-5" />
                  Chats
                </Link>
                <Link
                  to="/dashboard/profile"
                  className="flex items-center gap-3 px-4 py-2.5 text-slate-700 dark:text-slate-200 hover:bg-orange-50 dark:hover:bg-orange-900/20 hover:text-orange-600 dark:hover:text-orange-400 rounded-lg transition-all duration-200"
                >
                  <User className="w-5 h-5" />
                  Profile
                </Link>
                <Link
                  to="/dashboard/settings"
                  className="flex items-center gap-3 px-4 py-2.5 text-slate-700 dark:text-slate-200 hover:bg-orange-50 dark:hover:bg-orange-900/20 hover:text-orange-600 dark:hover:text-orange-400 rounded-lg transition-all duration-200"
                >
                  <Settings className="w-5 h-5" />
                  Settings
                </Link>
              </nav>
            </div>
          </div>

          {/* Content Area */}
          <div className="flex-1">
            <Routes>
              <Route path="/" element={
                <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-8">
                  <h2 className="text-3xl font-bold bg-gradient-to-r from-orange-600 to-purple-600 bg-clip-text text-transparent mb-4">
                    Welcome, {user?.displayName}!
                  </h2>
                  <p className="text-slate-600 dark:text-slate-400">Start a new chat or continue an existing conversation.</p>
                </div>
              } />
              <Route path="/profile" element={
                <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-8">
                  <h2 className="text-3xl font-bold bg-gradient-to-r from-orange-600 to-purple-600 bg-clip-text text-transparent mb-4">Profile</h2>
                  {/* Add profile content here */}
                </div>
              } />
              <Route path="/settings" element={
                <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-8">
                  <h2 className="text-3xl font-bold bg-gradient-to-r from-orange-600 to-purple-600 bg-clip-text text-transparent mb-4">Settings</h2>
                  {/* Add settings content here */}
                </div>
              } />
            </Routes>
          </div>
        </div>
      </main>

      {/* Modals */}
      <NewChatModal
        isOpen={isNewChatModalOpen}
        onClose={() => setIsNewChatModalOpen(false)}
        onSubmit={() => {}}
        isLoading={false}
      />

      <SearchModal
        isOpen={isSearchModalOpen}
        onClose={() => setIsSearchModalOpen(true)}
        chats={[]}
        onSelectChat={() => {}}
      />
    </div>
  );
}