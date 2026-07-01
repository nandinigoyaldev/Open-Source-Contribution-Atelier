import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api";
import { encryptNoteContent, decryptNoteContent } from "../../lib/notesCrypto";
import { Lock, Save, Plus, Trash2, X } from "lucide-react";

interface EncryptedNote {
  id: number;
  title: string;
  encrypted_content: string;
  iv: string;
  created_at: string;
  updated_at: string;
}

interface DecryptedNote extends EncryptedNote {
  plaintext: string;
}

export function NotesWidget() {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [activeNote, setActiveNote] = useState<DecryptedNote | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [editingTitle, setEditingTitle] = useState("");

  const { data: encryptedNotes = [], isLoading } = useQuery<EncryptedNote[]>({
    queryKey: ["privateNotes"],
    queryFn: () => fetchApi("/notes/"),
  });

  const [decryptedNotes, setDecryptedNotes] = useState<DecryptedNote[]>([]);

  // Decrypt notes whenever encrypted data changes
  useEffect(() => {
    const decryptAll = async () => {
      const decrypted = await Promise.all(
        encryptedNotes.map(async (note) => {
          const plaintext = await decryptNoteContent(
            note.encrypted_content,
            note.iv,
          );
          return { ...note, plaintext };
        }),
      );
      setDecryptedNotes(decrypted);
    };
    if (encryptedNotes.length > 0) {
      decryptAll();
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDecryptedNotes([]);
    }
  }, [encryptedNotes]);

  const saveNoteMutation = useMutation({
    mutationFn: async ({
      title,
      content,
      id,
    }: {
      title: string;
      content: string;
      id?: number;
    }) => {
      const { ciphertext, iv } = await encryptNoteContent(content);
      const payload = {
        title,
        encrypted_content: ciphertext,
        iv,
      };

      if (id) {
        return fetchApi(`/notes/${id}/`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        return fetchApi("/notes/", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["privateNotes"] });
      setActiveNote(null);
    },
  });

  const deleteNoteMutation = useMutation({
    mutationFn: async (id: number) => {
      return fetchApi(`/notes/${id}/`, { method: "DELETE" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["privateNotes"] });
      setActiveNote(null);
    },
  });

  const handleSave = () => {
    if (!editingContent.trim()) return;
    saveNoteMutation.mutate({
      title: editingTitle || "Untitled Note",
      content: editingContent,
      id: activeNote?.id,
    });
  };

  const handleNewNote = () => {
    setActiveNote(null);
    setEditingTitle("");
    setEditingContent("");
    setIsOpen(true);
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="bg-primary text-black font-black p-4 rounded-full border-4 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-1 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] transition-all flex items-center justify-center"
        >
          <Lock className="w-6 h-6 mr-2" />
          Private Notes
        </button>
      )}

      {isOpen && (
        <div className="bg-white dark:bg-[#151411] w-80 sm:w-96 rounded-2xl border-4 border-black dark:border-[#2e2924] shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] flex flex-col overflow-hidden max-h-[600px]">
          {/* Header */}
          <div className="bg-primary text-black p-4 border-b-4 border-black dark:border-[#2e2924] flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Lock className="w-5 h-5" />
              <h3 className="font-black text-lg">E2E Notes</h3>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleNewNote}
                className="hover:bg-black/10 p-1 rounded transition-colors"
              >
                <Plus className="w-5 h-5" />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="hover:bg-black/10 p-1 rounded transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Content area */}
          <div className="flex-1 overflow-y-auto bg-surface-lowest dark:bg-[#151411]">
            {activeNote !== null ||
            (!activeNote && editingContent !== "") ||
            editingTitle !== "" ? (
              // Editor View
              <div className="p-4 flex flex-col h-full gap-4">
                <input
                  type="text"
                  placeholder="Note Title"
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  className="font-black text-xl bg-transparent border-b-2 border-black dark:border-[#2e2924] pb-2 focus:outline-none dark:text-[#f0ebe2] dark:placeholder-[#c4bbae]"
                />
                <textarea
                  placeholder="Write your secret notes here... They are encrypted in your browser before saving!"
                  value={editingContent}
                  onChange={(e) => setEditingContent(e.target.value)}
                  className="flex-1 resize-none bg-transparent border-none focus:outline-none text-sm font-bold dark:text-[#c4bbae]"
                />
                <div className="flex justify-between mt-auto">
                  <button
                    onClick={() => setActiveNote(null)}
                    className="text-muted font-bold text-xs uppercase hover:text-black dark:hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saveNoteMutation.isPending}
                    className="flex items-center gap-2 bg-black text-white px-4 py-2 rounded-lg font-black text-sm disabled:opacity-50"
                  >
                    <Save className="w-4 h-4" />
                    {saveNoteMutation.isPending
                      ? "Encrypting..."
                      : "Save Securely"}
                  </button>
                </div>
              </div>
            ) : (
              // List View
              <div className="p-4 space-y-3 h-[400px]">
                {isLoading ? (
                  <p className="text-center text-muted font-bold mt-10">
                    Loading keys...
                  </p>
                ) : decryptedNotes.length === 0 ? (
                  <div className="text-center mt-10 space-y-2">
                    <p className="text-4xl">🔐</p>
                    <p className="font-bold text-muted dark:text-[#c4bbae] text-sm">
                      No notes yet.
                    </p>
                    <p className="text-xs text-muted dark:text-[#c4bbae]">
                      Everything you write here is AES-GCM encrypted. Even the
                      database admins can't read it.
                    </p>
                  </div>
                ) : (
                  decryptedNotes.map((note) => (
                    <div
                      key={note.id}
                      className="bg-white dark:bg-[#1f1c18] p-3 rounded-xl border-2 border-black dark:border-[#2e2924] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-1 transition-transform group cursor-pointer"
                      onClick={() => {
                        setActiveNote(note);
                        setEditingTitle(note.title);
                        setEditingContent(note.plaintext);
                      }}
                    >
                      <div className="flex justify-between items-start">
                        <h4 className="font-black text-sm dark:text-[#f0ebe2] truncate">
                          {note.title}
                        </h4>
                        <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteNoteMutation.mutate(note.id);
                            }}
                            className="text-red-500 hover:bg-red-100 p-1 rounded"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-muted dark:text-[#c4bbae] truncate mt-1">
                        {note.plaintext}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
