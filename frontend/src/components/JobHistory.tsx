import React, { useState, useEffect } from 'react';
import { Table, Badge, Button, Spinner, Alert } from 'react-bootstrap';
import { apiService } from '../services/api';
import { ProcessingJob } from '../types';
import StatusIndicator from './StatusIndicator';

interface JobHistoryProps {
  onJobSelect: (jobId: string) => void;
}

const JobHistory: React.FC<JobHistoryProps> = ({ onJobSelect }) => {
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      const jobsData = await apiService.listJobs();
      setJobs(jobsData);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load job history');
    } finally {
      setLoading(false);
    }
  };


  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 80) return 'success';
    if (confidence >= 20) return 'warning';
    return 'danger';
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString();
  };

  if (loading) {
    return (
      <div className="loading-container text-center py-5">
        <Spinner animation="border" variant="primary" />
        <p className="mt-3 text-muted">Loading job history...</p>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="danger" className="mb-4">
        <Alert.Heading>
          <i className="fas fa-exclamation-triangle me-2"></i>
          Error Loading Job History
        </Alert.Heading>
        {error}
      </Alert>
    );
  }

  return (
    <div className="job-history-container">
      <div className="job-history-header mb-4">
        <div className="d-flex justify-content-between align-items-center">
          <h5 className="mb-0">
            <i className="fas fa-history me-2 text-primary"></i>
            Job History
          </h5>
          <Button variant="outline-primary" size="sm" onClick={loadJobs}>
            <i className="fas fa-sync-alt me-1"></i>
            Refresh
          </Button>
        </div>
      </div>

      {jobs.length === 0 ? (
        <div className="empty-state text-center py-5">
          <i className="fas fa-history fa-3x text-muted mb-3"></i>
          <h6 className="text-muted">No jobs found</h6>
          <p className="text-muted">Upload a PDF, scan, or photo to get started with analysis.</p>
        </div>
      ) : (
        <div className="table-responsive">
          <Table hover className="modern-table">
            <thead>
              <tr>
                <th>
                  <i className="fas fa-file-pdf me-2"></i>
                  File
                </th>
                <th>
                  <i className="fas fa-info-circle me-2"></i>
                  Status
                </th>
                <th>
                  <i className="fas fa-file-alt me-2"></i>
                  Pages
                </th>
                <th>
                  <i className="fas fa-chart-line me-2"></i>
                  Confidence
                </th>
                <th>
                  <i className="fas fa-clock me-2"></i>
                  Created
                </th>
                <th>
                  <i className="fas fa-cog me-2"></i>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.job_id} className="job-row">
                  <td>
                    <div className="file-info">
                      <div className="filename">
                        <i className={`${job.file_type === 'image' ? 'fas fa-file-image text-info' : 'fas fa-file-pdf text-danger'} me-2`}></i>
                        <strong>{job.filename}</strong>
                      </div>
                      <small className="job-id text-muted">
                        ID: {job.job_id.substring(0, 8)}...
                      </small>
                    </div>
                  </td>
                  <td>
                    <div className="status-badges">
                      <StatusIndicator status={job.status} size="sm" />
                      {job.auto_approved && job.status === 'completed' && (
                        <Badge bg="success" className="ms-2">
                          <i className="fas fa-check me-1"></i>
                          Auto-Approved
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td>
                    <div className="page-info">
                      {job.status === 'processing' ? (
                        <span className="processing-pages">
                          <i className="fas fa-cog fa-spin me-1"></i>
                          {job.processed_pages} / {job.total_pages}
                        </span>
                      ) : (
                        <span className="total-pages">
                          <i className="fas fa-file-alt me-1"></i>
                          {job.total_pages}
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    {job.overall_confidence > 0 && (
                      <Badge bg={getConfidenceColor(job.overall_confidence)}>
                        <i className="fas fa-chart-line me-1"></i>
                        {job.overall_confidence.toFixed(1)}%
                      </Badge>
                    )}
                  </td>
                  <td>
                    <small className="created-date">
                      <i className="fas fa-clock me-1"></i>
                      {formatDate(job.created_at)}
                    </small>
                  </td>
                  <td>
                    <Button
                      variant="outline-primary"
                      size="sm"
                      onClick={() => onJobSelect(job.job_id)}
                      disabled={job.status === 'failed'}
                      className="view-button"
                    >
                      <i className="fas fa-eye me-1"></i>
                      View
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </div>
  );
};

export default JobHistory;
