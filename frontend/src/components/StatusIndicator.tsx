import React from 'react';
import { Badge } from 'react-bootstrap';

interface StatusIndicatorProps {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  size?: 'sm' | 'md' | 'lg';
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ status, size = 'md' }) => {
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'pending':
        return {
          variant: 'secondary',
          icon: 'fas fa-clock',
          text: 'Pending',
          className: 'status-pending'
        };
      case 'processing':
        return {
          variant: 'primary',
          icon: 'fas fa-cog fa-spin',
          text: 'Processing',
          className: 'status-processing'
        };
      case 'completed':
        return {
          variant: 'success',
          icon: 'fas fa-check-circle',
          text: 'Completed',
          className: 'status-completed'
        };
      case 'failed':
        return {
          variant: 'danger',
          icon: 'fas fa-exclamation-circle',
          text: 'Failed',
          className: 'status-failed'
        };
      default:
        return {
          variant: 'secondary',
          icon: 'fas fa-question-circle',
          text: 'Unknown',
          className: 'status-unknown'
        };
    }
  };

  const config = getStatusConfig(status);
  const sizeClass = size === 'sm' ? 'status-sm' : size === 'lg' ? 'status-lg' : 'status-md';

  return (
    <Badge 
      bg={config.variant} 
      className={`status-indicator ${config.className} ${sizeClass}`}
    >
      <i className={config.icon}></i>
      <span className="ms-1">{config.text}</span>
    </Badge>
  );
};

export default StatusIndicator;

