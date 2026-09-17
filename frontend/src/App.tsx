import React, { useState } from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import { ThemeProvider } from './contexts/ThemeContext';
import ModernNavbar from './components/ModernNavbar';
import ModernCard from './components/ModernCard';
import UploadForm from './components/UploadForm';
import ProcessingStatus from './components/ProcessingStatus';
import ResultsDashboard from './components/ResultsDashboard';
import JobHistory from './components/JobHistory';
import BatchStatus from './components/BatchStatus';
import { BatchUploadResponse, UploadResponse } from './types';
import './styles/modern-theme.css';

function App() {
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [currentBatchId, setCurrentBatchId] = useState<string | null>(null);
  const [showResults, setShowResults] = useState(false);
  const [activeTab, setActiveTab] = useState('upload');

  const handleUploadSuccess = (response: UploadResponse) => {
    setCurrentJobId(response.job_id);
    setCurrentBatchId(null);
    setShowResults(false);
    setActiveTab('status');
  };

  const handleBatchStarted = (response: BatchUploadResponse) => {
    setCurrentBatchId(response.batch_id);
    setCurrentJobId(response.job_ids?.[0] || null);
    setShowResults(false);
    setActiveTab('status');
  };

  const handleJobComplete = (jobId: string) => {
    if (currentBatchId) {
      return;
    }
    setShowResults(true);
    setActiveTab('results');
  };

  const handleJobSelect = (jobId: string) => {
    setCurrentJobId(jobId);
    setShowResults(true);
    setActiveTab('results');
  };

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'upload':
        return (
          <ModernCard 
            title="Upload files for analysis" 
            icon="fas fa-upload"
            variant="info"
            className="fade-in"
          >
            <UploadForm
              onUploadSuccess={handleUploadSuccess}
              onBatchStarted={handleBatchStarted}
            />
          </ModernCard>
        );

      case 'status':
        return (
          <ModernCard 
            title={currentBatchId ? 'Batch Processing' : 'Processing Status'} 
            icon="fas fa-cog"
            variant="info"
            className="fade-in"
          >
            {currentBatchId ? (
              <BatchStatus batchId={currentBatchId} onJobSelect={handleJobSelect} />
            ) : currentJobId ? (
              <ProcessingStatus
                jobId={currentJobId}
                onComplete={handleJobComplete}
              />
            ) : (
              <div className="text-center py-5">
                <i className="fas fa-info-circle fa-3x text-muted mb-3"></i>
                <h5>No Job Selected</h5>
                <p className="text-muted">Upload files or a SharePoint library to see processing status.</p>
              </div>
            )}
          </ModernCard>
        );

      case 'results':
        return (
          <ModernCard 
            title="Analysis Results" 
            icon="fas fa-chart-bar"
            variant="success"
            className="fade-in"
          >
            {currentJobId && showResults ? (
              <ResultsDashboard jobId={currentJobId} />
            ) : (
              <div className="text-center py-5">
                <i className="fas fa-chart-bar fa-3x text-muted mb-3"></i>
                <h5>No Results Available</h5>
                <p className="text-muted">
                  {!currentJobId 
                    ? "Upload a PDF, scan, or photo to see analysis results." 
                    : "Processing is still in progress. Results will appear here when complete."
                  }
                </p>
              </div>
            )}
          </ModernCard>
        );

      case 'history':
        return (
          <ModernCard 
            title="Job History" 
            icon="fas fa-history"
            variant="default"
            className="fade-in"
          >
            <JobHistory onJobSelect={handleJobSelect} />
          </ModernCard>
        );

      default:
        return null;
    }
  };

  return (
    <ThemeProvider>
      <div className="App">
        <ModernNavbar 
          activeTab={activeTab} 
          onTabChange={handleTabChange}
        />

        <Container fluid className="main-container">
          <Row>
            <Col>
              <div className="content-wrapper">
                {renderTabContent()}
              </div>
            </Col>
          </Row>
        </Container>
      </div>
    </ThemeProvider>
  );
}

export default App;
