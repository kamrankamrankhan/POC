import React, { useEffect, useState } from 'react';
import { Alert, Badge, Button, ProgressBar, Spinner, Table } from 'react-bootstrap';
import { apiService } from '../services/api';
import { BatchJob } from '../types';
import StatusIndicator from './StatusIndicator';

interface BatchStatusProps {
  batchId: string;
  onJobSelect: (jobId: string) => void;
}

const BatchStatus: React.FC<BatchStatusProps> = ({ batchId, onJobSelect }) => {
  const [batch, setBatch] = useState<BatchJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await apiService.getBatch(batchId);
        if (!cancelled) {
          setBatch(data);
          setError(null);
        }
        return data.status === 'completed' || data.status === 'failed';
      } catch (err: any) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'Failed to load batch status');
        }
        return false;
      }
    };

    load();
    const interval = setInterval(async () => {
      const done = await load();
      if (done) {
        clearInterval(interval);
      }
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [batchId]);

  if (error) {
    return <Alert variant="danger">{error}</Alert>;
  }

  if (!batch) {
    return (
      <div className="text-center py-5">
        <Spinner animation="border" variant="primary" />
        <p className="mt-3 text-muted">Loading batch status...</p>
      </div>
    );
  }

  const total = batch.total_files || batch.files.length;
  const processed = batch.processed_files;
  const percent = total > 0 ? Math.round((processed / total) * 100) : 0;

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div>
          <h5 className="mb-1">Batch processing</h5>
          <div className="text-muted">
            {batch.source === 'sharepoint' ? 'SharePoint library' : 'Local upload'}
            {batch.source_url ? ` · ${batch.source_url}` : ''}
          </div>
        </div>
        <StatusIndicator status={batch.status} size="lg" />
      </div>

      <div className="mb-3">
        <div className="d-flex justify-content-between mb-1">
          <span>Files processed</span>
          <strong>
            {processed} / {total || '…'}
          </strong>
        </div>
        <ProgressBar now={percent} animated={batch.status === 'processing'} label={`${percent}%`} />
      </div>

      {batch.error_message && <Alert variant="danger">{batch.error_message}</Alert>}

      <Table hover responsive>
        <thead>
          <tr>
            <th>File</th>
            <th>Status</th>
            <th>Confidence</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {batch.files.map((file, index) => (
            <tr key={`${file.relative_path}-${index}`}>
              <td>
                <i
                  className={`${
                    file.file_type === 'image' ? 'fas fa-file-image text-info' : 'fas fa-file-pdf text-danger'
                  } me-2`}
                ></i>
                <strong>{file.filename}</strong>
                {file.relative_path && file.relative_path !== file.filename && (
                  <div className="small text-muted">{file.relative_path}</div>
                )}
                {file.error_message && (
                  <div className="small text-danger">{file.error_message}</div>
                )}
              </td>
              <td>
                <StatusIndicator status={file.status} size="sm" />
              </td>
              <td>
                {file.overall_confidence != null && file.overall_confidence > 0 && (
                  <Badge bg={file.overall_confidence >= 80 ? 'success' : file.overall_confidence >= 20 ? 'warning' : 'danger'}>
                    {file.overall_confidence.toFixed(1)}%
                  </Badge>
                )}
              </td>
              <td className="text-end">
                <Button
                  size="sm"
                  variant="outline-primary"
                  disabled={!file.job_id || file.status !== 'completed'}
                  onClick={() => file.job_id && onJobSelect(file.job_id)}
                >
                  View
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
};

export default BatchStatus;
