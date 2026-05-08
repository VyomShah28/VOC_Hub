'use client';

import { useEffect, useState, useRef } from 'react';
import { DashboardLayout } from '@/components/dashboard-layout';
import { ChartCard } from '@/components/chart-card';
import { DataTable } from '@/components/data-table';
import api from '@/lib/api';

export default function KnowledgeBasePage() {
  const [files, setFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const fetchFiles = async () => {
    try {
      const response = await api.get('/knowledge/files');
      setFiles(response.data);
    } catch (error) {
      console.error('Failed to fetch knowledge files:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadMessage('Only PDF files are supported for the Knowledge Base.');
      event.target.value = '';
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    setIsUploading(true);
    setUploadMessage(`Uploading ${file.name}...`);

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
      const response = await fetch(`${baseUrl}/knowledge/upload`, {
        method: 'POST',
        body: formData,
      });

      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(payload?.detail || 'Upload failed');
      }

      setUploadMessage(payload?.message || 'Upload completed successfully.');
      await fetchFiles(); // Refresh the list
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : 'Failed to upload file.');
    } finally {
      setIsUploading(false);
      event.target.value = '';
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDownload = (fileId: number) => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
    window.open(`${baseUrl}/knowledge/download/${fileId}`, '_blank');
  };

  const handleView = (fileId: number) => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
    window.open(`${baseUrl}/knowledge/view/${fileId}`, '_blank');
  };

  const formattedData = files.map((f) => ({
    filename: f.filename,
    size: (f.size_bytes / 1024).toFixed(2) + ' KB',
    uploaded_at: new Date(f.uploaded_at).toLocaleString(),
    action: (
      <div className="flex space-x-2">
        <button 
          onClick={() => handleView(f.id)}
          className="px-3 py-1 bg-secondary text-foreground border border-border rounded-md text-xs font-semibold hover:bg-secondary/80 transition"
        >
          View
        </button>
        <button 
          onClick={() => handleDownload(f.id)}
          className="px-3 py-1 bg-primary text-primary-foreground rounded-md text-xs font-semibold hover:bg-primary/90 transition"
        >
          Download
        </button>
      </div>
    )
  }));

  return (
    <DashboardLayout>
      <div className="space-y-8">
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Model Knowledge Base</p>
          <div className="bg-card border border-border rounded-xl p-8 shadow-sm flex flex-col items-center justify-center space-y-4">
            <h3 className="text-lg font-medium text-foreground">Increase Model Knowledge</h3>
            <p className="text-sm text-muted-foreground text-center max-w-md">
              Upload PDF documents such as company policies, product manuals, or strategic guidelines. 
              The AI will automatically learn from these documents and use them to answer your questions in "Ask Your Data".
            </p>
            
            <div className="mt-4 w-full max-w-md">
              <label className="flex flex-col items-center justify-center w-full h-32 px-4 transition-colors bg-secondary/30 border-2 border-dashed rounded-lg appearance-none cursor-pointer hover:border-primary focus:outline-none border-border">
                <span className="flex items-center space-x-2">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <span className="font-medium text-muted-foreground">
                    {isUploading ? "Processing PDF..." : "Drop PDF to Upload, or Click Here"}
                  </span>
                </span>
                <input 
                  type="file" 
                  name="file_upload" 
                  className="hidden" 
                  accept=".pdf" 
                  onChange={handleUpload}
                  disabled={isUploading}
                  ref={fileInputRef}
                />
              </label>
              {uploadMessage && (
                <p className={`mt-2 text-xs text-center ${uploadMessage.includes('failed') || uploadMessage.includes('Only') ? 'text-red-500' : 'text-green-500'}`}>
                  {uploadMessage}
                </p>
              )}
            </div>
          </div>
        </div>

        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Indexed Documents</p>
          <ChartCard title="Uploaded PDFs">
            {loading ? (
              <div className="p-4 text-sm text-muted-foreground">Loading files...</div>
            ) : files.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">No documents indexed yet. Upload a PDF above.</div>
            ) : (
              <DataTable
                columns={[
                  { key: 'filename', label: 'Filename' },
                  { key: 'size', label: 'Size' },
                  { key: 'uploaded_at', label: 'Upload Date' },
                  { key: 'action', label: 'Actions' },
                ]}
                data={formattedData}
              />
            )}
          </ChartCard>
        </div>
      </div>
    </DashboardLayout>
  );
}
