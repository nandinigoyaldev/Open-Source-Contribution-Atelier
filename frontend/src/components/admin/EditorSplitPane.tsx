import React, { useMemo } from "react";
import SimpleMDE from "react-simplemde-editor";
import "easymde/dist/easymde.min.css";
import { Group, Panel, Separator } from "react-resizable-panels";
import { LessonDraftData } from "../../hooks/useContentDraft";
import { LessonPreview } from "./LessonPreview";
import api from "../../api";

interface EditorSplitPaneProps {
  lesson: LessonDraftData;
  onChangeContent: (content: string) => void;
}

export function EditorSplitPane({
  lesson,
  onChangeContent,
}: EditorSplitPaneProps) {
  const mdeOptions = useMemo(
    () => ({
      spellChecker: false,
      placeholder: "Write your lesson markdown content here...",
      status: false,
      autosave: {
        enabled: false,
        uniqueId: `lesson-mde-${lesson.id || "new"}`,
      },
      uploadImage: true,
      imageUploadFunction: (
        file: File,
        onSuccess: (url: string) => void,
        onError: (error: string) => void,
      ) => {
        const formData = new FormData();
        formData.append("file", file);
        api
          .post<{ url: string }>("/uploads/", formData, {
            headers: { "Content-Type": "multipart/form-data" },
          })
          .then((res) => {
            if (res.data?.url) {
              onSuccess(res.data.url);
            } else {
              onError("Image upload failed");
            }
          })
          .catch((err) => {
            onError(err.message || "Failed to upload image");
          });
      },
    }),
    [lesson.id],
  );

  return (
    <div className="w-full h-[calc(100vh-220px)] min-h-[500px]">
      <Group direction="horizontal">
        <Panel defaultSize={50} minSize={30}>
          <div className="w-full h-full p-2 bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2e2924] rounded-xl flex flex-col overflow-hidden shadow-sm">
            <div className="text-xs font-bold text-muted dark:text-[#a0988c] px-3 py-1.5 border-b border-black/10 dark:border-[#2e2924] flex items-center justify-between">
              <span>Markdown Editor (EasyMDE)</span>
              <span className="text-[10px] text-accent">
                Drag & drop images supported
              </span>
            </div>
            <div className="flex-1 overflow-y-auto p-1 text-text dark:text-[#f0ebe2]">
              <SimpleMDE
                value={lesson.content || ""}
                onChange={onChangeContent}
                options={mdeOptions as any}
              />
            </div>
          </div>
        </Panel>

        <Separator className="w-2 mx-1 rounded bg-black/10 dark:bg-[#2e2924] hover:bg-accent transition-colors cursor-col-resize flex items-center justify-center">
          <div className="w-1 h-8 bg-black/30 dark:bg-white/30 rounded-full" />
        </Separator>

        <Panel defaultSize={50} minSize={30}>
          <LessonPreview lesson={lesson} />
        </Panel>
      </Group>
    </div>
  );
}
