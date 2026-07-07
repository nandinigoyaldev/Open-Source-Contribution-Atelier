import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FolderGit2, Code2, Play, X, FileCode, Users } from 'lucide-react';
import api from '../api';

// Types based on backend serializers
interface TemplateCategory {
  id: string;
  name: string;
  description: string;
}

interface TemplateFile {
  id: string;
  path: string;
  content: string;
}

interface ProjectTemplate {
  id: string;
  category: string; // ID of category
  name: string;
  description: string;
  language: string;
  tags: string[];
  is_official: boolean;
  use_count: number;
  files: TemplateFile[];
  author?: { id: string; username: string };
}

const TemplateMarketplacePage: React.FC = () => {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<ProjectTemplate[]>([]);
  const [categories, setCategories] = useState<TemplateCategory[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedTemplate, setSelectedTemplate] = useState<ProjectTemplate | null>(null);
  const [isInstantiating, setIsInstantiating] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [templatesRes, categoriesRes] = await Promise.all([
          api.get('/sandbox/templates/'),
          api.get('/sandbox/template-categories/')
        ]);
        setTemplates(templatesRes.data);
        setCategories(categoriesRes.data);
      } catch (err) {
        console.error('Failed to fetch templates', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleInstantiate = async (templateId: string) => {
    setIsInstantiating(true);
    try {
      const res = await api.post(`/sandbox/templates/${templateId}/instantiate/`);
      if (res.data && res.data.project_id) {
        navigate(`/sandbox/${res.data.project_id}`);
      }
    } catch (err) {
      console.error('Failed to instantiate template', err);
      alert('Error creating project from template.');
      setIsInstantiating(false);
    }
  };

  const filteredTemplates = templates.filter((t) => {
    const matchesSearch = t.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          t.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || t.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-extrabold tracking-tight text-gray-900 dark:text-white sm:text-5xl md:text-6xl">
            <span className="block text-indigo-600 dark:text-indigo-400">Starter Workspace</span>
            <span className="block">Library</span>
          </h1>
          <p className="mt-3 max-w-md mx-auto text-base text-gray-500 dark:text-gray-400 sm:text-lg md:mt-5 md:text-xl md:max-w-3xl">
            Launch your next project instantly with pre-configured templates for your favorite frameworks and languages.
          </p>
        </div>

        {/* Filters and Search */}
        <div className="flex flex-col sm:flex-row justify-between items-center space-y-4 sm:space-y-0 sm:space-x-4">
          <div className="relative flex-1 max-w-lg w-full">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              className="block w-full pl-10 pr-3 py-3 border border-gray-300 dark:border-gray-700 rounded-lg leading-5 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm transition-shadow shadow-sm"
              placeholder="Search templates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="flex space-x-2 overflow-x-auto w-full sm:w-auto pb-2 sm:pb-0">
            <button
              onClick={() => setSelectedCategory('all')}
              className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                selectedCategory === 'all' 
                ? 'bg-indigo-600 text-white' 
                : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 shadow-sm border border-gray-200 dark:border-gray-700'
              }`}
            >
              All
            </button>
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                  selectedCategory === cat.id 
                  ? 'bg-indigo-600 text-white' 
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 shadow-sm border border-gray-200 dark:border-gray-700'
                }`}
              >
                {cat.name}
              </button>
            ))}
          </div>
        </div>

        {/* Templates Grid */}
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredTemplates.map((template) => (
            <div 
              key={template.id}
              onClick={() => setSelectedTemplate(template)}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden hover:shadow-md transition-all cursor-pointer group flex flex-col"
            >
              <div className="p-5 flex-1">
                <div className="flex justify-between items-start">
                  <div className="p-2 bg-indigo-50 dark:bg-indigo-900/30 rounded-lg text-indigo-600 dark:text-indigo-400">
                    <FolderGit2 className="h-6 w-6" />
                  </div>
                  {template.is_official && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                      Official
                    </span>
                  )}
                </div>
                <h3 className="mt-4 text-lg font-semibold text-gray-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                  {template.name}
                </h3>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 line-clamp-2">
                  {template.description}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {template.tags.slice(0, 3).map(tag => (
                    <span key={tag} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
              <div className="px-5 py-3 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-100 dark:border-gray-700 flex justify-between items-center">
                <div className="flex items-center text-xs text-gray-500 dark:text-gray-400">
                  <Users className="h-3.5 w-3.5 mr-1" />
                  {template.use_count} uses
                </div>
                <div className="text-xs font-medium text-gray-500 dark:text-gray-400 flex items-center">
                  <Code2 className="h-3.5 w-3.5 mr-1" />
                  {template.language}
                </div>
              </div>
            </div>
          ))}
          {filteredTemplates.length === 0 && (
            <div className="col-span-full py-12 text-center text-gray-500 dark:text-gray-400">
              No templates found matching your criteria.
            </div>
          )}
        </div>
      </div>

      {/* Preview Modal */}
      {selectedTemplate && (
        <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity backdrop-blur-sm" aria-hidden="true" onClick={() => setSelectedTemplate(null)}></div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white dark:bg-gray-800 rounded-2xl text-left overflow-hidden shadow-2xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl w-full border border-gray-200 dark:border-gray-700">
              <div className="absolute top-0 right-0 pt-4 pr-4">
                <button
                  type="button"
                  className="bg-white dark:bg-gray-800 rounded-md text-gray-400 hover:text-gray-500 focus:outline-none"
                  onClick={() => setSelectedTemplate(null)}
                >
                  <span className="sr-only">Close</span>
                  <X className="h-6 w-6" />
                </button>
              </div>
              <div className="px-6 pt-8 pb-6">
                <div className="sm:flex sm:items-start">
                  <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-indigo-100 dark:bg-indigo-900/50 sm:mx-0 sm:h-12 sm:w-12">
                    <FolderGit2 className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left flex-1">
                    <h3 className="text-2xl leading-6 font-bold text-gray-900 dark:text-white flex items-center" id="modal-title">
                      {selectedTemplate.name}
                      {selectedTemplate.is_official && (
                        <span className="ml-3 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                          Official
                        </span>
                      )}
                    </h3>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {selectedTemplate.description}
                      </p>
                    </div>
                    
                    <div className="mt-6">
                      <h4 className="text-sm font-medium text-gray-900 dark:text-white flex items-center">
                        <FileCode className="w-4 h-4 mr-2" />
                        Included Files
                      </h4>
                      <ul className="mt-2 border border-gray-200 dark:border-gray-700 rounded-md divide-y divide-gray-200 dark:divide-gray-700 bg-gray-50 dark:bg-gray-900/50 max-h-48 overflow-y-auto">
                        {selectedTemplate.files?.map((file) => (
                          <li key={file.id} className="pl-3 pr-4 py-2 flex items-center justify-between text-sm">
                            <div className="w-0 flex-1 flex items-center">
                              <span className="ml-2 flex-1 w-0 truncate text-gray-700 dark:text-gray-300 font-mono text-xs">
                                {file.path}
                              </span>
                            </div>
                          </li>
                        ))}
                        {(!selectedTemplate.files || selectedTemplate.files.length === 0) && (
                          <li className="pl-3 pr-4 py-3 flex items-center justify-center text-sm text-gray-500">
                            No starter files included.
                          </li>
                        )}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800/80 px-4 py-4 sm:px-6 sm:flex sm:flex-row-reverse border-t border-gray-200 dark:border-gray-700">
                <button
                  type="button"
                  className="w-full inline-flex justify-center rounded-lg border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 transition-colors"
                  onClick={() => handleInstantiate(selectedTemplate.id)}
                  disabled={isInstantiating}
                >
                  {isInstantiating ? (
                    <span className="flex items-center">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Creating Project...
                    </span>
                  ) : (
                    <span className="flex items-center">
                      <Play className="w-4 h-4 mr-2" />
                      Use this Template
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  className="mt-3 w-full inline-flex justify-center rounded-lg border border-gray-300 dark:border-gray-600 shadow-sm px-4 py-2 bg-white dark:bg-gray-800 text-base font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm transition-colors"
                  onClick={() => setSelectedTemplate(null)}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TemplateMarketplacePage;
