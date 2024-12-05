import React, { forwardRef, useImperativeHandle, useState, useRef, useEffect } from 'react';
import { Terminal as TerminalIcon } from 'lucide-react';

export interface TerminalRef {
  writeOutput: (text: string) => void;
  clear: () => void;
}

interface TerminalProps {
  className?: string;
  onCommand: (command: string) => Promise<void>;
}

interface TerminalLine {
  type: 'input' | 'output';
  content: string;
}

export const Terminal = forwardRef<TerminalRef, TerminalProps>(({ className = '', onCommand }, ref) => {
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [currentInput, setCurrentInput] = useState('');
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const terminalRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Initial welcome message
    setLines([
      { type: 'output', content: 'Welcome to the Repository Terminal' },
      { type: 'output', content: 'Type "help" for available commands' }
    ]);
  }, []);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [lines]);

  useImperativeHandle(ref, () => ({
    writeOutput: (text: string) => {
      setLines(prev => [...prev, { type: 'output', content: text }]);
    },
    clear: () => {
      setLines([]);
    }
  }));

  const handleCommand = async (command: string) => {
    if (!command.trim()) return;

    // Add command to history
    setLines(prev => [...prev, { type: 'input', content: `$ ${command}` }]);
    setCommandHistory(prev => [command, ...prev]);
    setHistoryIndex(-1);
    setCurrentInput('');

    // Execute command
    await onCommand(command);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleCommand(currentInput);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (historyIndex < commandHistory.length - 1) {
        const newIndex = historyIndex + 1;
        setHistoryIndex(newIndex);
        setCurrentInput(commandHistory[newIndex]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setCurrentInput(commandHistory[newIndex]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setCurrentInput('');
      }
    }
  };

  return (
    <div className={`flex flex-col bg-gray-900 text-white ${className}`}>
      <div className="flex items-center gap-2 px-4 py-2 bg-gray-800">
        <TerminalIcon className="w-4 h-4" />
        <span className="text-sm font-medium">Terminal</span>
      </div>
      <div
        ref={terminalRef}
        className="flex-1 overflow-y-auto p-4 font-mono text-sm"
        onClick={() => inputRef.current?.focus()}
      >
        {lines.map((line, index) => (
          <div
            key={index}
            className={`mb-1 ${
              line.type === 'input' ? 'text-green-400' : 'text-gray-300'
            }`}
          >
            {line.content}
          </div>
        ))}
        <div className="flex items-center">
          <span className="text-green-400 mr-2">$</span>
          <input
            ref={inputRef}
            type="text"
            value={currentInput}
            onChange={(e) => setCurrentInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent outline-none"
            autoFocus
          />
        </div>
      </div>
    </div>
  );
});

Terminal.displayName = 'Terminal';