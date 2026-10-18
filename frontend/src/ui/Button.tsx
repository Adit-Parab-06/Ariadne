import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';

export interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: 'filled' | 'tinted' | 'plain';
  color?: 'blue' | 'red' | 'gray' | 'green';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'filled',
  color = 'blue',
  size = 'md',
  className = '',
  children,
  disabled,
  ...props
}) => {
  const baseClasses =
    'inline-flex items-center justify-center font-medium transition-colors select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-blue focus-visible:ring-offset-2 disabled:opacity-40 disabled:pointer-events-none rounded-button';

  const sizeClasses = {
    sm: 'text-xs px-2.5 py-1 min-h-[30px] rounded-lg',
    md: 'text-sm px-3.5 py-1.5 min-h-[38px] rounded-xl',
    lg: 'text-base px-5 py-2.5 min-h-[44px] rounded-2xl',
  }[size];

  const variantColorClasses = {
    filled: {
      blue: 'bg-blue text-white shadow-sm hover:opacity-90 active:opacity-95',
      red: 'bg-red text-white shadow-sm hover:opacity-90 active:opacity-95',
      green: 'bg-green text-white shadow-sm hover:opacity-90 active:opacity-95',
      gray: 'bg-fill text-label hover:bg-fill/80 active:bg-fill/60',
    },
    tinted: {
      blue: 'bg-blue/15 text-blue hover:bg-blue/20 active:bg-blue/25',
      red: 'bg-red/15 text-red hover:bg-red/20 active:bg-red/25',
      green: 'bg-green/15 text-green hover:bg-green/20 active:bg-green/25',
      gray: 'bg-fill/50 text-label-2 hover:bg-fill/70 active:bg-fill',
    },
    plain: {
      blue: 'bg-transparent text-blue hover:bg-blue/10 active:bg-blue/15',
      red: 'bg-transparent text-red hover:bg-red/10 active:bg-red/15',
      green: 'bg-transparent text-green hover:bg-green/10 active:bg-green/15',
      gray: 'bg-transparent text-label-2 hover:text-label hover:bg-fill/30 active:bg-fill/50',
    },
  }[variant][color];

  return (
    <motion.button
      whileTap={{ scale: disabled ? 1 : 0.97 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      disabled={disabled}
      className={`${baseClasses} ${sizeClasses} ${variantColorClasses} ${className}`}
      {...props}
    >
      {children}
    </motion.button>
  );
};
