import React, { useState, useEffect, useRef } from 'react';
import { Loader2, FileCode, FolderOpen, ChevronRight, ChevronDown, Plus, Terminal as TerminalIcon } from 'lucide-react';
import Editor from "@monaco-editor/react";
import { Terminal, TerminalRef } from './Terminal';

interface CodePreviewProps {
  repoUrl: string;
  className?: string;
  onFileChange?: (path: string, content: string) => Promise<void>;
}

interface TreeNode {
  name: string;
  path: string;
  type: 'tree' | 'blob';
  children?: TreeNode[];
  content?: string;
}

interface FileOperation {
  path: string;
  status: 'loading' | 'saving' | 'done' | 'error';
  progress: number;
}

export function CodePreview({ repoUrl, className = '', onFileChange }: CodePreviewProps) {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [fileOperations, setFileOperations] = useState<Record<string, FileOperation>>({});
  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const [showTerminal, setShowTerminal] = useState(true);
  const terminalRef = useRef<TerminalRef>(null);
  const [currentDirectory, setCurrentDirectory] = useState('/');

  useEffect(() => {
    const fetchRepoContent = async () => {
      try {
        setLoading(true);
        const [owner, repo] = repoUrl.split('/').slice(-2);
        const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/git/trees/main?recursive=1`);
        const data = await response.json();
        
        const root: TreeNode[] = [];
        data.tree.forEach((item: any) => {
          const parts = item.path.split('/');
          let current = root;
          
          parts.forEach((part: string, index: number) => {
            const path = parts.slice(0, index + 1).join('/');
            const existing = current.find(node => node.name === part);
            
            if (!existing) {
              const node: TreeNode = {
                name: part,
                path,
                type: index === parts.length - 1 ? item.type : 'tree',
              };
              if (node.type === 'tree') {
                node.children = [];
              }
              current.push(node);
              current = node.children || [];
            } else {
              current = existing.children || [];
            }
          });
        });
        
        setTree(root);
        terminalRef.current?.writeOutput(`Repository cloned successfully: ${repoUrl}`);
        terminalRef.current?.writeOutput('Type "help" for available commands');
      } catch (error) {
        console.error('Error fetching repo content:', error);
        terminalRef.current?.writeOutput(`Error cloning repository: ${error.message}`);
      } finally {
        setLoading(false);
      }
    };

    fetchRepoContent();
  }, [repoUrl]);

  const fetchFileContent = async (path: string) => {
    try {
      const [owner, repo] = repoUrl.split('/').slice(-2);
      const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/contents/${path}`);
      const data = await response.json();
      const content = atob(data.content);
      setFileContent(content);
      setSelectedFile(path);
    } catch (error) {
      console.error('Error fetching file content:', error);
      terminalRef.current?.writeOutput(`Error fetching file content: ${error.message}`);
    }
  };

  const handleEditorChange = async (value: string | undefined) => {
    if (!selectedFile || !value || !onFileChange) return;
    
    try {
      setFileOperations(prev => ({
        ...prev,
        [selectedFile]: { path: selectedFile, status: 'saving', progress: 0 }
      }));
      
      await onFileChange(selectedFile, value);
      
      setFileOperations(prev => ({
        ...prev,
        [selectedFile]: { path: selectedFile, status: 'done', progress: 100 }
      }));
    } catch (error) {
      console.error('Error saving file:', error);
      setFileOperations(prev => ({
        ...prev,
        [selectedFile]: { path: selectedFile, status: 'error', progress: 0 }
      }));
    }
  };

  const handleCreateFile = async () => {
    if (!newFileName) return;
    
    try {
      const path = currentDirectory === '/' ? newFileName : `${currentDirectory}/${newFileName}`;
      await handleFileSystemOperation({
        type: 'create',
        path,
        timestamp: new Date(),
        user: 'current-user'
      }, terminalRef);
      
      setTree(prevTree => {
        const newTree = [...prevTree];
        const parts = path.split('/');
        let current = newTree;
        
        parts.forEach((part, index) => {
          if (index === parts.length - 1) {
            current.push({
              name: part,
              path,
              type: 'blob'
            });
          } else {
            let node = current.find(n => n.name === part);
            if (!node) {
              node = {
                name: part,
                path: parts.slice(0, index + 1).join('/'),
                type: 'tree',
                children: []
              };
              current.push(node);
            }
            current = node.children || [];
          }
        });
        
        return newTree;
      });
      
      setNewFileName('');
      setIsCreatingFile(false);
    } catch (error) {
      console.error('Error creating file:', error);
      terminalRef.current?.writeOutput(`Error creating file: ${error.message}`);
    }
  };
  const getFileLanguage = (filename: string): string => {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    const languageMap: { [key: string]: string } = {
      js: 'javascript',
      jsx: 'javascript',
      ts: 'typescript',
      tsx: 'typescript',
      py: 'python',
      java: 'java',
      cpp: 'cpp',
      c: 'c',
      cs: 'csharp',
      html: 'html',
      css: 'css',
      json: 'json',
      md: 'markdown',
      yaml: 'yaml',
      yml: 'yaml',
      xml: 'xml',
      sql: 'sql',
      sh: 'shell',
      bash: 'shell',
      php: 'php',
      go: 'go',
      rust: 'rust',
      rb: 'ruby',
      swift: 'swift',
      kt: 'kotlin',
      scala: 'scala',
      dart: 'dart',
      lua: 'lua',
      r: 'r',
      pl: 'perl',
      elm: 'elm',
      fs: 'fsharp',
      cmake: 'cmake',
      dockerfile: 'dockerfile',
    };
  
    return languageMap[extension] || 'plaintext';
  };

  const toggleFolder = (path: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const renderTree = (nodes: TreeNode[], level: number = 0) => {
    return (
      <div className={`${level > 0 ? 'ml-4' : ''}`}>
        {nodes.map((node) => (
          <div key={node.path} className="py-0.5">
            <div
              className={`flex items-center py-1 px-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded cursor-pointer text-sm ${
                selectedFile === node.path ? 'bg-gray-100 dark:bg-gray-800' : ''
              }`}
              onClick={() => {
                if (node.type === 'tree') {
                  toggleFolder(node.path);
                } else {
                  fetchFileContent(node.path);
                }
              }}
            >
              {node.type === 'tree' ? (
                <>
                  {expandedFolders.has(node.path) ? (
                    <ChevronDown className="w-3.5 h-3.5 mr-1 text-gray-500" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 mr-1 text-gray-500" />
                  )}
                  <FolderOpen className="w-3.5 h-3.5 mr-2 text-yellow-500" />
                </>
              ) : (
                <>
                  <FileCode className="w-3.5 h-3.5 mr-2 text-blue-500" />
                </>
              )}
              <span className="text-xs text-gray-700 dark:text-gray-300 truncate">{node.name}</span>
              {fileOperations[node.path] && (
                <div className="ml-2">
                  {fileOperations[node.path].status === 'saving' && (
                    <Loader2 className="w-3 h-3 animate-spin text-gray-500" />
                  )}
                </div>
              )}
            </div>
            {node.type === 'tree' && expandedFolders.has(node.path) && node.children && (
              renderTree(node.children, level + 1)
            )}
          </div>
        ))}
      </div>
    );
  };

  const executeCommand = async (command: string) => {
    // ... rest of the executeCommand function remains the same ...
  };
  
  const simulateNpmCommand = (duration: number) => {
    return new Promise(resolve => setTimeout(resolve, duration));
  };

  const findNodeByPath = (nodes: TreeNode[], path: string): TreeNode | null => {
    if (!path || path === '/') return { name: '/', path: '/', type: 'tree', children: nodes };
    
    const parts = path.split('/').filter(Boolean);
    let current: TreeNode[] = nodes;
    let result: TreeNode | null = null;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const found = current.find(node => node.name === part);
      
      if (!found) return null;
      
      if (i === parts.length - 1) {
        result = found;
      } else if (found.type === 'tree' && found.children) {
        current = found.children;
      } else {
        return null;
      }
    }

    return result;
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      <div className="flex-1 flex flex-col min-h-0">
        <div className="p-3 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Repository Files</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowTerminal(!showTerminal)}
                className="flex items-center gap-1.5 px-2 py-1 text-xs bg-gray-500 text-white rounded-md hover:bg-gray-600 transition-colors"
              >
                <TerminalIcon className="w-3.5 h-3.5" />
                {showTerminal ? 'Hide Terminal' : 'Show Terminal'}
              </button>
              <button
                onClick={() => setIsCreatingFile(true)}
                className="flex items-center gap-1.5 px-2 py-1 text-xs bg-primary-500 text-white rounded-md hover:bg-primary-600 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                New File
              </button>
            </div>
          </div>
        </div>
        <div className="flex-1 flex min-h-0">
          <div className="w-72 border-r border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col">
            <div className="flex-1 overflow-y-auto">
              {isCreatingFile && (
                <div className="m-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <input
                    type="text"
                    value={newFileName}
                    onChange={(e) => setNewFileName(e.target.value)}
                    placeholder="Enter file name..."
                    className="w-full p-1.5 text-xs border rounded-md mb-2"
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => setIsCreatingFile(false)}
                      className="px-2 py-1 text-xs text-gray-600 hover:text-gray-800"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleCreateFile}
                      className="px-2 py-1 text-xs bg-primary-500 text-white rounded-md hover:bg-primary-600"
                    >
                      Create
                    </button>
                  </div>
                </div>
              )}
              {loading ? (
                <div className="flex justify-center py-4">
                  <Loader2 className="w-5 h-5 text-primary-600 dark:text-primary-400 animate-spin" />
                </div>
              ) : (
                <div className="p-2">
                  {renderTree(tree)}
                </div>
              )}
            </div>
          </div>
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {selectedFile ? (
              <div className="flex-1 min-h-0">
                <Editor
                  height="100%"
                  defaultLanguage={getFileLanguage(selectedFile)}
                  theme="vs-dark"
                  value={fileContent || ''}
                  onChange={handleEditorChange}
                  options={{
                    minimap: { enabled: false },
                    fontSize: 12,
                    lineNumbers: 'on',
                    lineNumbersMinChars: 3,
                    lineDecorationsWidth: 0,
                    lineHeight: 1.5,
                    readOnly: false,
                    automaticLayout: true,
                    scrollBeyondLastLine: false,
                    renderLineHighlight: 'all',
                    padding: { top: 8, bottom: 8 },
                  }}
                />
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-gray-500 dark:text-gray-400">
                Select a file to view its contents
              </div>
            )}
          </div>
        </div>
      </div>
      {showTerminal && (
        <div className="h-56 border-t border-gray-200 dark:border-gray-700">
          <Terminal
            ref={terminalRef}
            onCommand={executeCommand}
            className="h-full"
          />
        </div>
      )}
    </div>
  );
}