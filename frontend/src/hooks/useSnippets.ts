import { useState, useEffect, useCallback } from "react";
import {
  SnippetCollection,
  CodeSnippet,
  fetchSnippetCollections,
  fetchSnippets,
  createSnippetCollection,
  deleteSnippetCollection,
  createSnippet,
  updateSnippet,
  deleteSnippet,
} from "../lib/api";
import toast from "react-hot-toast";

export function useSnippets() {
  const [collections, setCollections] = useState<SnippetCollection[]>([]);
  const [snippets, setSnippets] = useState<CodeSnippet[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Filters
  const [activeCollectionId, setActiveCollectionId] = useState<string | null>(
    null,
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [colls, snips] = await Promise.all([
        fetchSnippetCollections(),
        fetchSnippets({
          collection: activeCollectionId || undefined,
          search: searchQuery || undefined,
          is_favorite: showFavoritesOnly ? true : undefined,
        }),
      ]);
      setCollections(colls);
      setSnippets(snips);
    } catch (err) {
      console.error("Failed to load snippets", err);
    } finally {
      setIsLoading(false);
    }
  }, [activeCollectionId, searchQuery, showFavoritesOnly]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const addCollection = async (name: string, description: string = "") => {
    try {
      const coll = await createSnippetCollection({ name, description });
      setCollections((prev) => [coll, ...prev]);
      toast.success("Collection created");
      return coll;
    } catch (err) {
      toast.error("Failed to create collection");
      throw err;
    }
  };

  const removeCollection = async (id: string) => {
    try {
      await deleteSnippetCollection(id);
      setCollections((prev) => prev.filter((c) => c.id !== id));
      if (activeCollectionId === id) setActiveCollectionId(null);
      toast.success("Collection deleted");
    } catch (err) {
      toast.error("Failed to delete collection");
      throw err;
    }
  };

  const addSnippet = async (data: Partial<CodeSnippet>) => {
    try {
      const snip = await createSnippet(data);
      setSnippets((prev) => [snip, ...prev]);
      toast.success("Snippet saved");
      return snip;
    } catch (err) {
      toast.error("Failed to save snippet");
      throw err;
    }
  };

  const editSnippet = async (id: string, updates: Partial<CodeSnippet>) => {
    try {
      const snip = await updateSnippet(id, updates);
      setSnippets((prev) => prev.map((s) => (s.id === id ? snip : s)));
      toast.success("Snippet updated");
      return snip;
    } catch (err) {
      toast.error("Failed to update snippet");
      throw err;
    }
  };

  const removeSnippet = async (id: string) => {
    try {
      await deleteSnippet(id);
      setSnippets((prev) => prev.filter((s) => s.id !== id));
      toast.success("Snippet deleted");
    } catch (err) {
      toast.error("Failed to delete snippet");
      throw err;
    }
  };

  const toggleFavorite = async (snippet: CodeSnippet) => {
    return editSnippet(snippet.id, { is_favorite: !snippet.is_favorite });
  };

  const exportData = () => {
    const data = {
      collections,
      snippets,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `snippets_export_${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Export successful");
  };

  const importData = async (file: File) => {
    try {
      const text = await file.text();
      const data = JSON.parse(text);

      if (!data.collections || !data.snippets) {
        throw new Error("Invalid format");
      }

      // Simple implementation: Just create everything anew
      // A more robust implementation would try to map IDs or deduplicate
      const collMap = new Map();

      for (const coll of data.collections) {
        const newColl = await createSnippetCollection({
          name: coll.name,
          description: coll.description,
        });
        collMap.set(coll.id, newColl.id);
      }

      for (const snip of data.snippets) {
        const collId = snip.collection ? collMap.get(snip.collection) : null;
        await createSnippet({
          title: snip.title,
          description: snip.description,
          code: snip.code,
          language: snip.language,
          is_favorite: snip.is_favorite,
          tags: snip.tags,
          collection: collId,
        });
      }

      toast.success("Import successful");
      loadData();
    } catch (err) {
      console.error(err);
      toast.error("Failed to import data. Invalid file format.");
    }
  };

  return {
    collections,
    snippets,
    isLoading,
    activeCollectionId,
    setActiveCollectionId,
    searchQuery,
    setSearchQuery,
    showFavoritesOnly,
    setShowFavoritesOnly,
    addCollection,
    removeCollection,
    addSnippet,
    editSnippet,
    removeSnippet,
    toggleFavorite,
    exportData,
    importData,
    refresh: loadData,
  };
}
