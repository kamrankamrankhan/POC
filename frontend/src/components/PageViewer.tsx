import React, { useState, useEffect } from 'react';
import { Row, Col, Button, Spinner, Alert } from 'react-bootstrap';
import { apiService } from '../services/api';
import { PageImageResponse } from '../types';

interface PageViewerProps {
  jobId: string;
  totalPages: number;
  initialPage?: number;
  onPageChange?: (page: number) => void;
}

const PageViewer: React.FC<PageViewerProps> = ({
  jobId,
  totalPages,
  initialPage = 1,
  onPageChange
}) => {
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [pageData, setPageData] = useState<PageImageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(true);

  useEffect(() => {
    loadPage(currentPage);
  }, [currentPage, jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadPage = async (pageNumber: number) => {
    setLoading(true);
    setError(null);
    setImageLoading(true);

    try {
      const data = await apiService.getPageImage(jobId, pageNumber);
      setPageData(data);
      onPageChange?.(pageNumber);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load page');
    } finally {
      setLoading(false);
    }
  };

  const goToPage = (pageNumber: number) => {
    if (pageNumber >= 1 && pageNumber <= totalPages) {
      setCurrentPage(pageNumber);
    }
  };

  const goToPrevious = () => {
    if (currentPage > 1) {
      goToPage(currentPage - 1);
    }
  };

  const goToNext = () => {
    if (currentPage < totalPages) {
      goToPage(currentPage + 1);
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
      <div className="text-center">
        <Spinner animation="border" variant="primary" />
        <p className="mt-2">Loading page...</p>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="danger">
        <Alert.Heading>Error</Alert.Heading>
        {error}
      </Alert>
    );
  }

  return (
    <div>
      {/* Navigation */}
      <Row className="mb-3">
        <Col>
          <div className="d-flex justify-content-between align-items-center">
            <Button
              variant="outline-primary"
              onClick={goToPrevious}
              disabled={currentPage <= 1}
            >
              <i className="fas fa-chevron-left me-1"></i>
              Previous
            </Button>
            
            <div className="text-center">
              <h5 className="mb-0">
                Page {currentPage} of {totalPages}
              </h5>
              <small className="text-muted">
                Use arrow keys to navigate
              </small>
            </div>
            
            <Button
              variant="outline-primary"
              onClick={goToNext}
              disabled={currentPage >= totalPages}
            >
              Next
              <i className="fas fa-chevron-right ms-1"></i>
            </Button>
          </div>
        </Col>
      </Row>

      {/* Page Content */}
      <Row>
        <Col lg={8}>
          <div className="border rounded p-2 bg-light">
            {imageLoading && (
              <div className="text-center py-5">
                <Spinner animation="border" variant="primary" />
                <p className="mt-2">Loading image...</p>
              </div>
            )}
            <img
              src={apiService.getImageUrl(jobId, currentPage)}
              alt={`Page ${currentPage}`}
              className="img-fluid"
              style={{ 
                display: imageLoading ? 'none' : 'block',
                maxHeight: '70vh',
                width: '100%',
                objectFit: 'contain'
              }}
              onLoad={() => setImageLoading(false)}
              onError={() => setImageLoading(false)}
            />
          </div>
        </Col>
        
        <Col lg={4}>
          {pageData && (
            <div>
              <h6>Quality Analysis</h6>
              
              <div className="mb-3">
                <div className="d-flex justify-content-between align-items-center mb-2">
                  <span>Overall Confidence</span>
                  <span className={`badge bg-${getConfidenceColor(pageData.quality_result.confidence_score)}`}>
                    {pageData.quality_result.confidence_score.toFixed(1)}%
                  </span>
                </div>
              </div>

              <div className="mb-3">
                <h6>Quality Metrics</h6>
                <div className="small">
                  <div className="d-flex justify-content-between mb-1">
                    <span>Blur Detection:</span>
                    <span className={getScoreColor(pageData.quality_result.blur_score * 100)}>{(pageData.quality_result.blur_score * 100).toFixed(1)}%</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1">
                    <span>Orientation:</span>
                    <span className={getScoreColor(pageData.quality_result.orientation_score * 100)}>{(pageData.quality_result.orientation_score * 100).toFixed(1)}%</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1">
                    <span>Cropping:</span>
                    <span className={getScoreColor(pageData.quality_result.cropping_score * 100)}>{(pageData.quality_result.cropping_score * 100).toFixed(1)}%</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1">
                    <span>Color Consistency:</span>
                    <span className={getScoreColor(pageData.quality_result.color_consistency_score * 100)}>{(pageData.quality_result.color_consistency_score * 100).toFixed(1)}%</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1">
                    <span>DPI (Resolution):</span>
                    <span>{pageData.quality_result.actual_dpi.toFixed(0)} DPI</span>
                  </div>
                  <div className="d-flex justify-content-between mb-1">
                    <span>DPI Score:</span>
                    <span className={getScoreColor(pageData.quality_result.dpi_score * 100)}>{(pageData.quality_result.dpi_score * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>

              {pageData.quality_result.flags.length > 0 && (
                <div className="mb-3">
                  <h6>Quality Flags</h6>
                  <div>
                    {pageData.quality_result.flags.map((flag) => (
                      <span
                        key={flag}
                        className={`badge bg-${getFlagColor(flag)} me-1 mb-1`}
                      >
                        {flag.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-4">
                <Button
                  variant="outline-secondary"
                  size="sm"
                  onClick={() => window.open(apiService.getImageUrl(jobId, currentPage), '_blank')}
                >
                  <i className="fas fa-external-link-alt me-1"></i>
                  Open Full Size
                </Button>
              </div>
            </div>
          )}
        </Col>
      </Row>

      {/* Page Navigation */}
      <Row className="mt-3">
        <Col>
          <div className="d-flex justify-content-center gap-1">
            {Array.from({ length: Math.min(10, totalPages) }, (_, i) => {
              const pageNum = Math.max(1, currentPage - 5) + i;
              if (pageNum > totalPages) return null;
              
              return (
                <Button
                  key={pageNum}
                  variant={pageNum === currentPage ? 'primary' : 'outline-primary'}
                  size="sm"
                  onClick={() => goToPage(pageNum)}
                  style={{ minWidth: '40px' }}
                >
                  {pageNum}
                </Button>
              );
            })}
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default PageViewer;
