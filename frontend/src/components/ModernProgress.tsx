import React from 'react';
import { ProgressBar } from 'react-bootstrap';

interface ModernProgressProps {
  value: number;
  max?: number;
  label?: string;
  showPercentage?: boolean;
  animated?: boolean;
  variant?: 'primary' | 'success' | 'warning' | 'danger' | 'info';
  size?: 'sm' | 'md' | 'lg';
}

const ModernProgress: React.FC<ModernProgressProps> = ({
  value,
  max = 100,
  label,
  showPercentage = true,
  animated = true,
  variant = 'primary',
  size = 'md'
}) => {
  const percentage = max > 0 ? Math.round((value / max) * 100) : 0;
  const sizeClass = size === 'sm' ? 'progress-sm' : size === 'lg' ? 'progress-lg' : 'progress-md';

  return (
    <div className={`modern-progress ${sizeClass}`}>
      {label && (
        <div className="progress-label">
          <span className="label-text">{label}</span>
          {showPercentage && (
            <span className="percentage">{percentage}%</span>
          )}
        </div>
      )}
      <ProgressBar
        now={percentage}
        variant={variant}
        animated={animated}
        className="modern-progress-bar"
        label={showPercentage ? `${percentage}%` : undefined}
      />
    </div>
  );
};

export default ModernProgress;



