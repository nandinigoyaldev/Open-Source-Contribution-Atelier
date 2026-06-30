import React, { useState, useRef, useEffect } from 'react';
import { Upload, X, Play, Pause, CheckCircle, AlertTriangle } from 'lucide-react';
import { fetchApi } from '../../lib/api';

const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB

export function ChunkedUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'paused' | 'completed' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  
  const uploadRef = useRef<{ abort: boolean }>({ abort: false });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setStatus('idle');
      setProgress(0);
      setSessionId(null);
      setErrorMessage('');
    }
  };

  const startUpload = async () => {
    if (!file) return;

    try {
      setStatus('uploading');
      uploadRef.current.abort = false;
      
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      let currentSessionId = sessionId;
      let uploadedChunks: number[] = [];

      if (!currentSessionId) {
        // Init session
        const res = await fetchApi('/uploads/start/', {
          method: 'POST',
          body: JSON.stringify({
            filename: file.name,
            total_size: file.size,
            total_chunks: totalChunks
          })
        });
        currentSessionId = res.session_id;
        setSessionId(currentSessionId);
      } else {
        // Resume session
        const res = await fetchApi(`/uploads/status/${currentSessionId}/`);
        uploadedChunks = res.uploaded_chunks || [];
        setProgress(Math.floor((uploadedChunks.length / totalChunks) * 100));
      }

      for (let i = 0; i < totalChunks; i++) {
        if (uploadRef.current.abort) {
          setStatus('paused');
          return;
        }

        if (uploadedChunks.includes(i)) continue;

        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const chunk = file.slice(start, end);
        
        const formData = new FormData();
        formData.append('chunk', chunk);
        formData.append('chunk_index', i.toString());

        // We use fetch directly for FormData
        const token = localStorage.getItem("accessToken");
        const chunkRes = await fetch(`/api/uploads/chunk/${currentSessionId}/`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`
          },
          body: formData
        });

        if (!chunkRes.ok) throw new Error("Chunk upload failed");

        const newProgress = Math.floor(((i + 1) / totalChunks) * 100);
        setProgress(newProgress);
      }

      // Complete upload
      await fetchApi(`/uploads/complete/${currentSessionId}/`, {
        method: 'POST'
      });
      
      setStatus('completed');
      setProgress(100);

    } catch (err: any) {
      console.error(err);
      setStatus('error');
      setErrorMessage(err.message || 'Upload failed');
    }
  };

  const togglePause = () => {
    if (status === 'uploading') {
      uploadRef.current.abort = true;
    } else if (status === 'paused' || status === 'error') {
      startUpload();
    }
  };

  const cancelUpload = () => {
    uploadRef.current.abort = true;
    setFile(null);
    setStatus('idle');
    setProgress(0);
    setSessionId(null);
  };

  return (
    <div className="bg-white p-6 rounded-2xl border-4 border-black shadow-card max-w-md w-full dark:bg-[#151411] dark:border-[#2e2924] dark:shadow-none">
      <h2 className="text-2xl font-black mb-4">Upload Large File</h2>
      
      {!file ? (
        <div className="border-4 border-dashed border-black/20 rounded-xl p-8 text-center relative hover:bg-surface-low transition-colors dark:border-white/10 dark:hover:bg-[#1f1c18]">
          <input 
            type="file" 
            onChange={handleFileChange} 
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" 
          />
          <Upload className="mx-auto mb-2 text-muted" size={32} />
          <p className="font-bold text-muted">Click or drag file to upload</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="truncate pr-4 font-bold">
              {file.name} ({(file.size / (1024 * 1024)).toFixed(2)} MB)
            </div>
            {status !== 'completed' && (
              <button onClick={cancelUpload} className="text-red-500 hover:text-red-700 p-1">
                <X size={20} strokeWidth={3} />
              </button>
            )}
          </div>

          <div className="w-full bg-gray-200 rounded-full h-4 dark:bg-gray-800 border-2 border-black dark:border-[#2e2924]">
            <div 
              className={`h-full rounded-full transition-all duration-300 ${status === 'error' ? 'bg-red-500' : 'bg-primary'}`} 
              style={{ width: `${progress}%` }}
            />
          </div>
          
          <div className="flex items-center justify-between font-bold text-sm">
            <span className="text-muted">
              {status === 'idle' && 'Ready to upload'}
              {status === 'uploading' && `Uploading... ${progress}%`}
              {status === 'paused' && 'Paused'}
              {status === 'completed' && 'Upload Complete!'}
              {status === 'error' && errorMessage}
            </span>

            {status !== 'completed' && (
              <button 
                onClick={status === 'idle' ? startUpload : togglePause}
                className="bg-black text-white px-3 py-1 rounded-full text-xs hover:bg-gray-800 flex items-center gap-1 dark:bg-white dark:text-black"
              >
                {status === 'uploading' ? <><Pause size={14} /> Pause</> : <><Play size={14} /> {status === 'idle' ? 'Start' : 'Resume'}</>}
              </button>
            )}
            
            {status === 'completed' && (
              <CheckCircle className="text-green-500" size={20} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
