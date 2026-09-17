import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Badge, Button, Alert, Spinner, Modal } from 'react-bootstrap';
import { apiService } from '../services/api';
import { ProcessingResult, ReviewRequest } from '../types';
import PageViewer from './PageViewer';

interface ResultsDashboardProps {
  jobId: string;
}

const ResultsDashboard: React.FC<ResultsDashboardProps> = ({ jobId }) => {
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPageViewer, setShowPageViewer] = useState(false);
  const [selectedPage, setSelectedPage] = useState<number>(1);
  const [reviewing, setReviewing] = useState(false);

  useEffect(() => {
    const fetchResults = async () => {
      try {
        const resultData = await apiService.getJobResults(jobId);
        setResult(resultData);
        setError(null);
      } catch (err: any) {
        const errorMessage = err.response?.data?.detail || 'Failed to load results';
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [jobId]);


  const handleReview = async (reviewStatus: 'approved' | 'rejected') => {
    if (!result) return;

    setReviewing(true);
    try {
      const reviewRequest: ReviewRequest = {
        job_id: jobId,
        review_status: reviewStatus
      };
      
      await apiService.submitReview(reviewRequest);
      
      // Update local state
      setResult({
        ...result,
        review_status: reviewStatus
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit review');
    } finally {
      setReviewing(false);
    }
  };

  const handleGenerateReport = async (format: 'json' | 'csv') => {
    try {
      await apiService.generateReport({
        job_id: jobId,
        format: format
      });
      
      // Create download link
      const downloadUrl = apiService.downloadReport(jobId, `report.${format}`);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `${result?.filename}_report.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate report');
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 80) return 'success';
    if (confidence >= 20) return 'warning';
    return 'danger';
  };

  const getFlagColor = (flag: string) => {
    switch (flag) {
      case 'blur': return 'danger';
      case 'orientation': return 'warning';
      case 'cropping': return 'info';
      case 'color_consistency': return 'secondary';
      case 'low_dpi': return 'warning';
      default: return 'light';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-success'; // Green for excellent (80-100%)
    if (score >= 60) return 'text-warning'; // Yellow for good (60-79%)
    if (score >= 40) return 'text-info'; // Blue for fair (40-59%)
    return 'text-danger'; // Red for poor (0-39%)
  };

  if (loading) {
    return (
      <Card className="mb-4">
        <Card.Body className="text-center">
          <Spinner animation="border" variant="primary" />
          <p className="mt-2">Loading results...</p>
        </Card.Body>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="danger" className="mb-4">
        <Alert.Heading>
          <i className="fas fa-exclamation-triangle me-2"></i>
          Analysis Failed
        </Alert.Heading>
        <div className="error-message">
          {error}
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
    );
  }

  if (!result) {
    return (
      <Alert variant="warning">
        <Alert.Heading>No Results</Alert.Heading>
        No results found for this job.
      </Alert>
    );
  }

  return (
    <>
      <Card className="mb-4">
        <Card.Header>
          <Row className="align-items-center">
            <Col>
              <h4 className="mb-0">Analysis Results</h4>
            </Col>
            <Col xs="auto">
              <Badge bg={getConfidenceColor(result.overall_confidence)} className="fs-6">
                {result.overall_confidence.toFixed(1)}% Confidence
              </Badge>
            </Col>
          </Row>
        </Card.Header>
        <Card.Body>
          <Row className="mb-3">
            <Col md={6}>
              <strong>File:</strong> {result.filename}
            </Col>
            <Col md={6}>
              <strong>Total Pages:</strong> {result.total_pages}
              {(result.overall_heuristic_confidence != null || result.ml_enabled) && (
                <div className="text-muted mt-1">
                  <strong>Scoring:</strong>{' '}
                  Heuristic {(result.overall_heuristic_confidence ?? result.overall_confidence).toFixed(1)}%
                  {result.overall_ml_confidence != null && (
                    <> · ML {result.overall_ml_confidence.toFixed(1)}%</>
                  )}
                </div>
              )}
            </Col>
          </Row>
          
          <Row className="mb-3">
            <Col md={6}>
              <strong>Auto-Approved:</strong> 
              <Badge bg={result.auto_approved ? 'success' : 'secondary'} className="ms-2">
                {result.auto_approved ? 'Yes' : 'No'}
              </Badge>
            </Col>
            <Col md={6}>
              <strong>Review Status:</strong> 
              <Badge bg={result.review_status === 'approved' ? 'success' : 
                        result.review_status === 'rejected' ? 'danger' : 'warning'} className="ms-2">
                {result.review_status.charAt(0).toUpperCase() + result.review_status.slice(1)}
              </Badge>
            </Col>
          </Row>

          <div className="d-flex gap-2 mb-3">
            <Button
              variant="primary"
              onClick={() => setShowPageViewer(true)}
            >
              <i className="fas fa-eye me-1"></i>
              View Pages
            </Button>
            
            <Button
              variant="outline-success"
              onClick={() => handleGenerateReport('json')}
            >
              <i className="fas fa-download me-1"></i>
              Download JSON
            </Button>
            
            <Button
              variant="outline-info"
              onClick={() => handleGenerateReport('csv')}
            >
              <i className="fas fa-download me-1"></i>
              Download CSV
            </Button>
          </div>

          {result.review_status === 'pending' && (
            <div className="border-top pt-3">
              <h6>
                {result.auto_approved ? 'Document Review' : 'Manual Review Required'}
              </h6>
              <p className="text-muted">
                {result.auto_approved 
                  ? 'This document was auto-approved based on high confidence score, but you can still review it manually.'
                  : 'This document requires manual review due to low confidence score.'
                }
              </p>
              <div className="d-flex gap-2">
                <Button
                  variant="success"
                  onClick={() => handleReview('approved')}
                  disabled={reviewing}
                >
                  <i className="fas fa-check me-1"></i>
                  Approve
                </Button>
                <Button
                  variant="danger"
                  onClick={() => handleReview('rejected')}
                  disabled={reviewing}
                >
                  <i className="fas fa-times me-1"></i>
                  Reject
                </Button>
              </div>
            </div>
          )}
        </Card.Body>
      </Card>

      <Card>
        <Card.Header>
          <h5 className="mb-0">Page Analysis</h5>
        </Card.Header>
        <Card.Body>
          <Row>
            {result.pages.map((page) => (
              <Col key={page.page_number} md={6} lg={4} className="mb-3">
                <Card className="h-100">
                  <Card.Body className="p-2">
                    <div className="d-flex justify-content-between align-items-start mb-2">
                      <h6 className="mb-0">Page {page.page_number}</h6>
                      <Badge bg={getConfidenceColor(page.confidence_score)}>
                        {page.confidence_score.toFixed(1)}%
                      </Badge>
                    </div>
                    {(page.heuristic_confidence_score != null || page.ml_confidence_score != null) && (
                      <div className="small text-muted mb-2">
                        Heuristic {(page.heuristic_confidence_score ?? page.confidence_score).toFixed(1)}%
                        {page.ml_confidence_score != null && (
                          <> · ML {page.ml_confidence_score.toFixed(1)}%</>
                        )}
                      </div>
                    )}
                    
                    <div className="mb-2">
                      <img
                        src={apiService.getThumbnailUrl(jobId, page.page_number)}
                        alt={`Page ${page.page_number}`}
                        className="img-fluid rounded"
                        style={{ maxHeight: '150px', width: '100%', objectFit: 'cover' }}
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2RkZCIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjE0IiBmaWxsPSIjOTk5IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+SW1hZ2UgTm90IEZvdW5kPC90ZXh0Pjwvc3ZnPg==';
                        }}
                      />
                    </div>
                    
                    <div className="small">
                      <div className="mb-1">
                        <strong>Blur:</strong> <span className={getScoreColor(page.blur_score * 100)}>{(page.blur_score * 100).toFixed(1)}%</span>
                      </div>
                      <div className="mb-1">
                        <strong>Orientation:</strong> <span className={getScoreColor(page.orientation_score * 100)}>{(page.orientation_score * 100).toFixed(1)}%</span>
                      </div>
                      <div className="mb-1">
                        <strong>Cropping:</strong> <span className={getScoreColor(page.cropping_score * 100)}>{(page.cropping_score * 100).toFixed(1)}%</span>
                      </div>
                      <div className="mb-1">
                        <strong>Color:</strong> <span className={getScoreColor(page.color_consistency_score * 100)}>{(page.color_consistency_score * 100).toFixed(1)}%</span>
                      </div>
                      <div className="mb-2">
                        <strong>DPI:</strong> {page.actual_dpi ? page.actual_dpi.toFixed(0) : 'N/A'} DPI <span className={getScoreColor(page.dpi_score ? page.dpi_score * 100 : 0)}>({page.dpi_score ? (page.dpi_score * 100).toFixed(1) : 'N/A'}%)</span>
                      </div>
                      
                      {page.flags.length > 0 && (
                        <div>
                          <strong>Flags:</strong>
                          <div className="mt-1">
                            {page.flags.map((flag) => (
                              <Badge
                                key={flag}
                                bg={getFlagColor(flag)}
                                className="me-1 mb-1"
                                style={{ fontSize: '0.7em' }}
                              >
                                {flag.replace('_', ' ')}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </Card.Body>
                </Card>
              </Col>
            ))}
          </Row>
        </Card.Body>
      </Card>

      <Modal show={showPageViewer} onHide={() => setShowPageViewer(false)} size="xl">
        <Modal.Header closeButton>
          <Modal.Title>Page Viewer</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <PageViewer
            jobId={jobId}
            totalPages={result.total_pages}
            initialPage={selectedPage}
            onPageChange={setSelectedPage}
          />
        </Modal.Body>
      </Modal>
    </>
  );
};

export default ResultsDashboard;
