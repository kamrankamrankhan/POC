import axios from 'axios';
import {
  UploadResponse,
  ProcessingJob,
  ProcessingResult,
  ReviewRequest,
  ReviewResponse,
  PageImageResponse,
  ReportRequest,
  ReportResponse,
  BatchJob,
  BatchUploadResponse,
  SharePointPreviewResponse,
  SharePointProcessRequest
} from '../types';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const apiService = {
  // Upload PDF, scan, or photo
  uploadPDF: async (file: File, password?: string): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (password && password.trim()) {
      formData.append('password', password.trim());
    }
    
    const response = await api.post('/upload', formData, {
      timeout: 120000,
    });
    
    return response.data;
  },

  uploadBatch: async (files: File[], password?: string): Promise<BatchUploadResponse> => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    if (password && password.trim()) {
      formData.append('password', password.trim());
    }
    const response = await api.post('/upload/batch', formData, {
      timeout: 180000,
    });
    return response.data;
  },

  getBatch: async (batchId: string): Promise<BatchJob> => {
    const response = await api.get(`/batches/${batchId}`);
    return response.data;
  },

  previewSharePoint: async (payload: SharePointProcessRequest): Promise<SharePointPreviewResponse> => {
    const response = await api.post('/sharepoint/preview', payload, {
      timeout: 120000,
    });
    return response.data;
  },

  processSharePoint: async (payload: SharePointProcessRequest): Promise<BatchUploadResponse> => {
    const response = await api.post('/sharepoint/process', payload, {
      timeout: 120000,
    });
    return response.data;
  },

  // Get job status
  getJobStatus: async (jobId: string): Promise<ProcessingJob> => {
    const response = await api.get(`/status/${jobId}`);
    return response.data;
  },

  // Get job results
  getJobResults: async (jobId: string): Promise<ProcessingResult> => {
    const response = await api.get(`/results/${jobId}`);
    return response.data;
  },

  // Get page image
  getPageImage: async (jobId: string, pageNumber: number): Promise<PageImageResponse> => {
    const response = await api.get(`/page/${jobId}/${pageNumber}`);
    return response.data;
  },

  // Submit review
  submitReview: async (reviewRequest: ReviewRequest): Promise<ReviewResponse> => {
    const response = await api.post(`/review/${reviewRequest.job_id}`, reviewRequest);
    return response.data;
  },

  // Generate report
  generateReport: async (reportRequest: ReportRequest): Promise<ReportResponse> => {
    const response = await api.post(`/reports/${reportRequest.job_id}`, reportRequest);
    return response.data;
  },

  // List all jobs
  listJobs: async (): Promise<ProcessingJob[]> => {
    const response = await api.get('/jobs');
    return response.data;
  },

  // Get image URL
  getImageUrl: (jobId: string, pageNumber: number): string => {
    return `${API_BASE_URL}/images/${jobId}/${pageNumber}`;
  },

  // Get thumbnail URL
  getThumbnailUrl: (jobId: string, pageNumber: number): string => {
    return `${API_BASE_URL}/thumbnails/${jobId}/${pageNumber}`;
  },

  // Download report
  downloadReport: (jobId: string, filename: string): string => {
    return `${API_BASE_URL}/download/${jobId}/${filename}`;
  }
};

export default apiService;
