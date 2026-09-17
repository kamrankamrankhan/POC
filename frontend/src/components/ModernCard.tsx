import React from 'react';
import { Card } from 'react-bootstrap';

interface ModernCardProps {
  title?: string;
  icon?: string;
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'success' | 'warning' | 'info' | 'danger';
}

const ModernCard: React.FC<ModernCardProps> = ({ 
  title, 
  icon, 
  children, 
  className = '', 
  variant = 'default' 
}) => {
  const getVariantClass = () => {
    switch (variant) {
      case 'success': return 'modern-card-success';
      case 'warning': return 'modern-card-warning';
      case 'info': return 'modern-card-info';
      case 'danger': return 'modern-card-danger';
      default: return 'modern-card-default';
    }
  };

  return (
    <Card className={`modern-card ${getVariantClass()} ${className}`}>
      {title && (
        <Card.Header className="modern-card-header">
          {icon && <i className={`${icon} me-2`}></i>}
          <span className="card-title">{title}</span>
        </Card.Header>
      )}
      <Card.Body className="modern-card-body">
        {children}
      </Card.Body>
    </Card>
  );
};

export default ModernCard;

