import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertCircle, Info } from 'lucide-react';

export interface ToastProps {
  message: string;
  type?: 'success' | 'error' | 'info';
  isVisible: boolean;
}

export const Toast: React.FC<ToastProps> = ({
  message,
  type = 'success',
  isVisible,
}) => {
  const icon = {
    success: <CheckCircle2 className="w-4 h-4 text-green" />,
    error: <AlertCircle className="w-4 h-4 text-red" />,
    info: <Info className="w-4 h-4 text-blue" />,
  }[type];

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ y: 20, opacity: 0, scale: 0.95 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          exit={{ y: 20, opacity: 0, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 450, damping: 30 }}
          className="fixed bottom-6 right-6 z-50 flex items-center space-x-2.5 px-4 py-2.5 rounded-full bg-bg-2 border apple-border shadow-2xl backdrop-blur-md"
        >
          {icon}
          <span className="text-xs font-semibold text-label">{message}</span>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
