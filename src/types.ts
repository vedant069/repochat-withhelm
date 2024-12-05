export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface Chat {
  id: string;
  repoUrl: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export interface ChatState {
  chats: Chat[];
  currentChatId: string | null;
  isLoading: boolean;
  error: string | null;
}

export interface TreeNode {
  name: string;
  path: string;
  type: 'tree' | 'blob';
  children?: TreeNode[];
  content?: string;
}

export interface FileOperation {
  path: string;
  status: 'loading' | 'saving' | 'done' | 'error';
  progress: number;
}

export interface TabInfo {
  path: string;
  label: string;
}