import React from 'react';
import { motion } from 'framer-motion';

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  className?: string;
}

export const Toggle: React.FC<ToggleProps> = ({
  checked,
  onChange,
  label,
  disabled = false,
  className = '',
}) => {
  return (
    <label
      className={`inline-flex items-center space-x-3 cursor-pointer select-none min-h-[44px] ${
        disabled ? 'opacity-40 cursor-not-allowed' : ''
      } ${className}`}
    >
      <div
        role="switch"
        aria-checked={checked}
        onClick={() => !disabled && onChange(!checked)}
        className={`w-12 h-7 flex items-center rounded-full p-1 transition-colors ${
          checked ? 'bg-green' : 'bg-fill'
        }`}
      >
        <motion.div
          animate={{ x: checked ? 20 : 0 }}
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          className="w-5 h-5 bg-white rounded-full shadow-md pointer-events-none"
        />
      </div>
      {label && <span className="text-sm font-medium text-label">{label}</span>}
    </label>
  );
};
