import React from 'react';
import { Compass, BookOpen, Send, Sparkles, Activity } from 'lucide-react';

export interface AgentAvatarProps {
  role: 'scout' | 'archivist' | 'responder' | 'synthesizer' | 'orchestrator' | string;
  size?: 'sm' | 'md' | 'lg';
  isWorking?: boolean;
  className?: string;
}

export const AgentAvatar: React.FC<AgentAvatarProps> = ({
  role,
  size = 'md',
  isWorking = false,
  className = '',
}) => {
  const normRole = role.toLowerCase();

  const iconConfig = {
    scout: {
      icon: Compass,
      bg: 'bg-blue/15 text-blue border-blue/30',
      pulse: 'bg-blue',
    },
    archivist: {
      icon: BookOpen,
      bg: 'bg-purple/15 text-purple border-purple/30',
      pulse: 'bg-purple',
    },
    responder: {
      icon: Send,
      bg: 'bg-orange/15 text-orange border-orange/30',
      pulse: 'bg-orange',
    },
    synthesizer: {
      icon: Sparkles,
      bg: 'bg-teal/15 text-teal border-teal/30',
      pulse: 'bg-teal',
    },
    orchestrator: {
      icon: Activity,
      bg: 'bg-indigo/15 text-indigo border-indigo/30',
      pulse: 'bg-indigo',
    },
  }[normRole] || {
    icon: Activity,
    bg: 'bg-fill text-label-2 border-transparent',
    pulse: 'bg-label-2',
  };

  const IconComponent = iconConfig.icon;

  const sizeClasses = {
    sm: 'w-7 h-7 rounded-lg text-xs',
    md: 'w-9 h-9 rounded-xl text-sm',
    lg: 'w-12 h-12 rounded-2xl text-base',
  }[size];

  const iconSizes = {
    sm: 'w-3.5 h-3.5',
    md: 'w-4.5 h-4.5',
    lg: 'w-6 h-6',
  }[size];

  return (
    <div className="relative inline-flex flex-shrink-0">
      <div
        className={`flex items-center justify-center border ${iconConfig.bg} ${sizeClasses} ${className}`}
      >
        <IconComponent className={iconSizes} />
      </div>

      {isWorking && (
        <span className="absolute -top-1 -right-1 flex h-3 w-3">
          <span
            className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${iconConfig.pulse}`}
          />
          <span
            className={`relative inline-flex rounded-full h-3 w-3 border-2 border-bg ${iconConfig.pulse}`}
          />
        </span>
      )}
    </div>
  );
};
