import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: 'elevated' | 'sunken' | 'glass';
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'elevated',
  className = '',
  ...props
}) => {
  const variantStyles = {
    elevated: 'bg-bg-2 border apple-border shadow-apple',
    sunken: 'bg-fill/40 border border-transparent',
    glass: 'apple-glass border apple-border shadow-apple',
  }[variant];

  return (
    <div
      className={`rounded-card p-4 transition-all ${variantStyles} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
