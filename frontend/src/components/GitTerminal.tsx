import React, { useState } from 'react';
import './GitTerminal.css';

interface File {
  name: string;
  content: string;
}

export function GitTerminal() {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState<string[]>(['Welcome to Git Sandbox!', 'Type `git init` to start']);
  const [files, setFiles] = useState<File[]>([]);
  const [isGitInit, setIsGitInit] = useState(false);
  const [currentDir, setCurrentDir] = useState('/');

  const handleCommand = (cmd: string) => {
    const parts = cmd.trim().split(' ');
    const command = parts[0];
    const args = parts.slice(1);

    switch (command) {
      case 'git':
        handleGitCommand(args);
        break;
      case 'ls':
        handleLs();
        break;
      case 'cat':
        handleCat(args);
        break;
      case 'touch':
        handleTouch(args);
        break;
      case 'echo':
        handleEcho(args);
        break;
      case 'clear':
        setOutput([]);
        break;
      case 'help':
        showHelp();
        break;
      default:
        addOutput(`Unknown command: ${command}`);
    }
    setInput('');
  };

  const handleGitCommand = (args: string[]) => {
    if (args[0] === 'init') {
      setIsGitInit(true);
      addOutput('✅ Initialized empty Git repository');
      setFiles([{ name: '.git', content: 'Git repository' }]);
    } else if (args[0] === 'status') {
      if (!isGitInit) {
        addOutput('❌ Not a git repository');
        return;
      }
      const untracked = files.filter(f => f.name !== '.git');
      if (untracked.length === 0) {
        addOutput('✅ Nothing to commit, working tree clean');
      } else {
        addOutput('📝 Untracked files:');
        untracked.forEach(f => addOutput(`  ${f.name}`));
      }
    } else if (args[0] === 'add') {
      if (!isGitInit) {
        addOutput('❌ Not a git repository');
        return;
      }
      const fileName = args[1];
      if (!fileName) {
        addOutput('❌ Please specify a file');
        return;
      }
      const file = files.find(f => f.name === fileName);
      if (!file) {
        addOutput(`❌ File ${fileName} not found`);
        return;
      }
      addOutput(`✅ ${fileName} added to staging`);
    } else if (args[0] === 'commit') {
      if (!isGitInit) {
        addOutput('❌ Not a git repository');
        return;
      }
      const msg = args.slice(2).join(' ');
      if (!msg) {
        addOutput('❌ Please specify a commit message');
        return;
      }
      addOutput(`✅ Commit: "${msg}" created`);
    } else {
      addOutput(`❌ Unknown git command: ${args[0]}`);
    }
  };

  const handleLs = () => {
    if (files.length === 0) {
      addOutput('(empty)');
      return;
    }
    files.forEach(f => addOutput(`📁 ${f.name}`));
  };

  const handleCat = (args: string[]) => {
    const fileName = args[0];
    if (!fileName) {
      addOutput('❌ Please specify a file');
      return;
    }
    const file = files.find(f => f.name === fileName);
    if (!file) {
      addOutput(`❌ File ${fileName} not found`);
      return;
    }
    addOutput(file.content || '(empty file)');
  };

  const handleTouch = (args: string[]) => {
    const fileName = args[0];
    if (!fileName) {
      addOutput('❌ Please specify a file name');
      return;
    }
    if (files.find(f => f.name === fileName)) {
      addOutput(`⚠️ File ${fileName} already exists`);
      return;
    }
    setFiles([...files, { name: fileName, content: '' }]);
    addOutput(`✅ Created file: ${fileName}`);
  };

  const handleEcho = (args: string[]) => {
    const content = args.join(' ');
    if (!content) {
      addOutput('❌ Please specify content');
      return;
    }
    // Check if it's redirecting to a file (echo "content" > file.txt)
    const redirectIndex = args.indexOf('>');
    if (redirectIndex !== -1) {
      const fileName = args[redirectIndex + 1];
      if (fileName) {
        const fileContent = args.slice(0, redirectIndex).join(' ');
        const existing = files.find(f => f.name === fileName);
        if (existing) {
          existing.content = fileContent;
          setFiles([...files]);
        } else {
          setFiles([...files, { name: fileName, content: fileContent }]);
        }
        addOutput(`✅ Written to ${fileName}`);
        return;
      }
    }
    addOutput(content);
  };

  const showHelp = () => {
    addOutput('📚 Available commands:');
    addOutput('  git init      - Initialize git repository');
    addOutput('  git status    - Show working tree status');
    addOutput('  git add <file> - Add file to staging');
    addOutput('  git commit -m "msg" - Commit changes');
    addOutput('  ls            - List files');
    addOutput('  cat <file>    - View file content');
    addOutput('  touch <file>  - Create new file');
    addOutput('  echo "text"   - Display text');
    addOutput('  clear         - Clear terminal');
    addOutput('  help          - Show this help');
  };

  const addOutput = (text: string) => {
    setOutput(prev => [...prev, text]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && input.trim()) {
      addOutput(`$ ${input}`);
      handleCommand(input);
    }
  };

  return (
    <div className="git-terminal">
      <div className="terminal-header">
        <span>💻 Git Sandbox</span>
        <span className="terminal-status">
          {isGitInit ? '🟢 Git initialized' : '⚪ Not a git repo'}
        </span>
      </div>
      <div className="terminal-output">
        {output.map((line, i) => (
          <div key={i} className="terminal-line">{line}</div>
        ))}
        <div className="terminal-input-line">
          <span className="prompt">$</span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command..."
            autoFocus
            className="terminal-input"
          />
        </div>
      </div>
    </div>
  );
}