import React, { useState, useEffect, useCallback } from 'react';
import { 
  Project, ProjectFile, fetchProjects, createProject, 
  createProjectFile, updateProjectFile, deleteProjectFile 
} from '../../lib/api';
import { ProjectExplorer } from './ProjectExplorer';
import { CodeEditor } from './CodeEditor';

export function ProjectWorkspace() {
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Load project on mount
  useEffect(() => {
    async function loadWorkspace() {
      try {
        let projects = await fetchProjects();
        if (projects.length === 0) {
          // Auto-create default project
          const defaultProject = await createProject("Default Project");
          await createProjectFile(defaultProject.id, 'src/index.js', '// Welcome to your new project workspace!\n');
          projects = [defaultProject];
        }
        
        const activeProject = projects[0];
        setProject(activeProject);
        
        // Fetch files for this project (though they might be returned nested in the project API, let's just use the nested array if present)
        if (activeProject.files) {
          setFiles(activeProject.files);
          if (activeProject.files.length > 0) {
            setActiveFileId(activeProject.files[0].id);
          }
        }
      } catch (err) {
        console.error("Failed to load workspace", err);
      } finally {
        setLoading(false);
      }
    }
    loadWorkspace();
  }, []);

  const handleCreateFile = async (path: string) => {
    if (!project) return;
    try {
      const ext = path.split('.').pop() || '';
      let lang = 'javascript';
      if (ext === 'py') lang = 'python';
      if (ext === 'rs') lang = 'rust';
      if (ext === 'json') lang = 'json';
      if (ext === 'ts' || ext === 'tsx') lang = 'typescript';

      const newFile = await createProjectFile(project.id, path, '', lang);
      setFiles(prev => [...prev, newFile]);
      setActiveFileId(newFile.id);
    } catch (err) {
      console.error("Failed to create file", err);
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      await deleteProjectFile(fileId);
      setFiles(prev => prev.filter(f => f.id !== fileId));
      if (activeFileId === fileId) {
        setActiveFileId(null);
      }
    } catch (err) {
      console.error("Failed to delete file", err);
    }
  };

  const activeFile = files.find(f => f.id === activeFileId);

  // Debounced auto-save
  const handleCodeChange = useCallback((newCode: string) => {
    if (!activeFileId) return;
    
    // Optimistic UI update
    setFiles(prev => prev.map(f => f.id === activeFileId ? { ...f, content: newCode } : f));
    
    // Fire and forget API save
    updateProjectFile(activeFileId, { content: newCode }).catch(err => {
      console.error("Failed to save file", err);
    });
  }, [activeFileId]);

  if (loading) {
    return <div className="h-full flex items-center justify-center text-gray-500">Loading Workspace...</div>;
  }

  return (
    <div className="flex h-full border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden bg-white dark:bg-[#1a1a1a]">
      <ProjectExplorer 
        files={files} 
        activeFileId={activeFileId} 
        onSelectFile={setActiveFileId}
        onCreateFile={handleCreateFile}
        onDeleteFile={handleDeleteFile}
      />
      
      <div className="flex-1 flex flex-col h-full bg-[#1e1e1e]">
        {activeFile ? (
          <>
            <div className="flex items-center px-4 py-2 border-b border-gray-800 bg-[#252525]">
              <span className="text-sm text-gray-300 font-mono">{activeFile.path}</span>
            </div>
            <div className="flex-1 overflow-auto bg-[#151411]">
              <CodeEditor 
                code={activeFile.content} 
                onChange={handleCodeChange}
                language={activeFile.language}
                minHeight="100%"
              />
            </div>
          </>
        ) : (
          <div className="h-full flex items-center justify-center text-gray-500">
            Select a file to edit
          </div>
        )}
      </div>
    </div>
  );
}
