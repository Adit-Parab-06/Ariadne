import React from 'react';
import { ChevronRight } from 'lucide-react';

export interface ListGroupProps {
  title?: string;
  footer?: string;
  children: React.ReactNode;
  className?: string;
}

export const ListGroup: React.FC<ListGroupProps> = ({
  title,
  footer,
  children,
  className = '',
}) => {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {title && (
        <h4 className="text-[12px] font-semibold uppercase tracking-wider text-label-2 px-3">
          {title}
        </h4>
      )}
      <div className="bg-bg-2 border apple-border rounded-2xl overflow-hidden divide-y divide-sep shadow-sm">
        {children}
      </div>
      {footer && (
        <p className="text-[11px] text-label-3 px-3">
          {footer}
        </p>
      )}
    </div>
  );
};

export interface ListRowProps {
  icon?: React.ReactNode;
  label: React.ReactNode;
  subtitle?: React.ReactNode;
  value?: React.ReactNode;
  onClick?: () => void;
  showChevron?: boolean;
  className?: string;
}

export const ListRow: React.FC<ListRowProps> = ({
  icon,
  label,
  subtitle,
  value,
  onClick,
  showChevron,
  className = '',
}) => {
  const isClickable = Boolean(onClick);

  return (
    <div
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick?.();
        }
      }}
      className={`flex items-center justify-between px-3.5 py-3 transition-colors min-h-[44px] ${
        isClickable
          ? 'cursor-pointer hover:bg-fill/30 active:bg-fill/50 focus:outline-none focus:bg-fill/40'
          : ''
      } ${className}`}
    >
      <div className="flex items-center space-x-3 overflow-hidden">
        {icon && <div className="flex-shrink-0 text-label-2">{icon}</div>}
        <div className="flex flex-col overflow-hidden text-left">
          <span className="text-sm font-medium text-label truncate">{label}</span>
          {subtitle && (
            <span className="text-xs text-label-2 truncate mt-0.5">{subtitle}</span>
          )}
        </div>
      </div>

      <div className="flex items-center space-x-2 flex-shrink-0 ml-3">
        {value && <div className="text-xs text-label-2 font-medium">{value}</div>}
        {(showChevron || isClickable) && (
          <ChevronRight className="w-4 h-4 text-label-3 flex-shrink-0" />
        )}
      </div>
    </div>
  );
};
