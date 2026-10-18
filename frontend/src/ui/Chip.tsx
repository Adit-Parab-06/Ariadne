import React from 'react';

export interface ChipProps {
  label: string;
  type?: 'service' | 'person' | 'incident' | 'doc' | 'procedure' | 'decision' | 'customer' | 'team' | string;
  onClick?: () => void;
  active?: boolean;
  className?: string;
}

export const Chip: React.FC<ChipProps> = ({
  label,
  type = 'service',
  onClick,
  active = false,
  className = '',
}) => {
  // Derive type from ID prefix if label starts with it
  let resolvedType = type.toLowerCase();
  if (label.startsWith('svc_')) resolvedType = 'service';
  else if (label.startsWith('per_')) resolvedType = 'person';
  else if (label.startsWith('inc_')) resolvedType = 'incident';
  else if (label.startsWith('doc_')) resolvedType = 'doc';
  else if (label.startsWith('prc_')) resolvedType = 'procedure';
  else if (label.startsWith('dec_')) resolvedType = 'decision';
  else if (label.startsWith('cus_')) resolvedType = 'customer';
  else if (label.startsWith('team_')) resolvedType = 'team';

  const typeStyles: Record<string, string> = {
    service: 'bg-blue/15 text-blue border-blue/30 hover:bg-blue/25',
    person: 'bg-purple/15 text-purple border-purple/30 hover:bg-purple/25',
    incident: 'bg-red/15 text-red border-red/30 hover:bg-red/25',
    doc: 'bg-orange/15 text-orange border-orange/30 hover:bg-orange/25',
    procedure: 'bg-green/15 text-green border-green/30 hover:bg-green/25',
    decision: 'bg-indigo/15 text-indigo border-indigo/30 hover:bg-indigo/25',
    customer: 'bg-teal/15 text-teal border-teal/30 hover:bg-teal/25',
    team: 'bg-indigo/15 text-indigo border-indigo/30 hover:bg-indigo/25',
    default: 'bg-fill text-label-2 border-transparent hover:bg-fill/80',
  };

  const style = typeStyles[resolvedType] || typeStyles.default;
  const isClickable = Boolean(onClick);

  return (
    <span
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick?.();
        }
      }}
      className={`inline-flex items-center font-mono text-xs px-2.5 py-1 rounded-full border transition-all select-none ${
        active ? 'ring-2 ring-blue font-bold shadow-sm' : ''
      } ${
        isClickable ? 'cursor-pointer' : ''
      } ${style} ${className}`}
    >
      {label}
    </span>
  );
};
