import React, { useState, useEffect } from 'react';
import { Alert, Spinner } from 'react-bootstrap';
import { apiService } from '../services/api';
import { ProcessingJob } from '../types';
import StatusIndicator from './StatusIndicator';
import ModernProgress from './ModernProgress';

interface ProcessingStatusProps {
  jobId: string;
  onComplete: (jobId: string) => void;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ jobId, onComplete }) => {
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const pollStatus = async () => {
      try {
        const jobData = await apiService.getJobStatus(jobId);
        setJob(jobData);
        setError(null);

        if (jobData.status === 'completed') {
          onComplete(jobId);
        }
        return jobData.status === 'completed' || jobData.status === 'failed';
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to get job status');
        return false;
      } finally {
        setLoading(false);
      }
    };

    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | undefined;

    const startPolling = async () => {
      const done = await pollStatus();
      if (cancelled || done) {
        return;
      }
      interval = setInterval(async () => {
        const finished = await pollStatus();
        if (finished && interval) {
          clearInterval(interval);
        }
      }, 2000);
    };

    startPolling();

    return () => {
      cancelled = true;
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [jobId, onComplete]);

  if (loading) {
    return (
      <div className="loading-container text-center py-5">
        <Spinner animation="border" variant="primary" />
        <p className="mt-3 text-muted">Loading job status...</p>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="danger" className="mb-4">
        <Alert.Heading>
          <i className="fas fa-exclamation-triangle me-2"></i>
          Error Loading Status
        </Alert.Heading>
        {error}
      </Alert>
    );
  }

  if (!job) {
    return (
      <Alert variant="warning" className="mb-4">
        <Alert.Heading>
          <i className="fas fa-search me-2"></i>
          Job Not Found
        </Alert.Heading>
        The requested job could not be found.
      </Alert>
    );
  }


  return (
    <div className="processing-status">
      <div className="status-header mb-4">
        <div className="d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Job Details</h5>
          <StatusIndicator status={job.status} size="lg" />
        </div>
      </div>

      <div className="job-info mb-4">
        <div className="info-item">
          <i className="fas fa-file-pdf me-2 text-primary"></i>
          <strong>File:</strong> {job.filename}
        </div>
        
        <div className="info-item">
          <i className="fas fa-fingerprint me-2 text-primary"></i>
          <strong>Job ID:</strong> <code className="job-id">{job.job_id}</code>
        </div>
      </div>

      {job.status === 'processing' && (
        <div className="processing-progress mb-4">
          <ModernProgress
            value={job.processed_pages || 0}
            max={job.total_pages || 0}
            label={
              job.total_pages > 0
                ? `Processing Pages (${job.processed_pages || 0} / ${job.total_pages})`
                : 'Preparing PDF…'
            }
            variant="primary"
            animated
            size="lg"
          />
        </div>
      )}

      {job.status === 'completed' && (
        <div className="completion-message mb-4">
          <div className="alert alert-success completion-alert">
            <div className="d-flex align-items-center">
              <i className="fas fa-check-circle fa-2x me-3 text-success"></i>
              <div>
                <h6 className="mb-1 text-success">
                  <strong>Analysis Complete!</strong>
                </h6>
                <p className="mb-0 text-muted">
                  Your PDF has been successfully analyzed. You can now view the detailed results.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {job.status === 'completed' && (
        <div className="completion-details mb-4">
          <div className="row g-3">
            <div className="col-md-6">
              <div className="stat-card">
                <i className="fas fa-file-alt me-2 text-info"></i>
                <div>
                  <div className="stat-label">Total Pages</div>
                  <div className="stat-value">{job.total_pages}</div>
                </div>
              </div>
            </div>
            <div className="col-md-6">
              <div className="stat-card">
                <i className="fas fa-chart-line me-2 text-success"></i>
                <div>
                  <div className="stat-label">Overall Confidence</div>
                  <div className="stat-value">
                    <StatusIndicator 
                      status={job.overall_confidence >= 80 ? 'completed' : job.overall_confidence >= 20 ? 'processing' : 'failed'} 
                      size="sm"
                    />
                    <span className="ms-2">{job.overall_confidence.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div className="mt-3">
            <div className="approval-status">
              <i className="fas fa-check-circle me-2 text-success"></i>
              <strong>Auto-Approved:</strong> 
              <StatusIndicator 
                status={job.auto_approved ? 'completed' : 'pending'} 
                size="sm"
              />
            </div>
          </div>
        </div>
      )}

      {job.status === 'failed' && job.error_message && (
        <Alert variant="danger" className="mb-4">
          <Alert.Heading>
            <i className="fas fa-exclamation-triangle me-2"></i>
            Upload Failed
          </Alert.Heading>
          <div className="error-message">
            {job.error_message}
          </div>
          <hr />
          <div className="error-help">
            <strong>What you can do:</strong>
            <ul className="mb-0 mt-2">
              <li>If this is a bank statement or encrypted PDF, enter the password on the Upload tab</li>
              <li>Check that the file is not damaged</li>
              <li>Try uploading a different PDF file</li>
              <li>Ensure the file size is under 50MB</li>
              <li>Use the Upload PDF tab to try another file</li>
            </ul>
          </div>
        </Alert>
      )}

      <div className="timestamps">
        <div className="timestamp-item">
          <i className="fas fa-clock me-2 text-muted"></i>
          <strong>Created:</strong> {new Date(job.created_at * 1000).toLocaleString()}
        </div>
        {job.completed_at && (
          <div className="timestamp-item">
            <i className="fas fa-check-circle me-2 text-success"></i>
            <strong>Completed:</strong> {new Date(job.completed_at * 1000).toLocaleString()}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProcessingStatus;
