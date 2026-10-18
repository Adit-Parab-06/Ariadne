import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

export interface SheetProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  maxWidth?: string;
}

export const Sheet: React.FC<SheetProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = 'max-w-lg',
}) => {
  const sheetRef = useRef<HTMLDivElement>(null);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
          {/* Dimmed backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm -z-10"
          />

          {/* Sheet panel */}
          <motion.div
            ref={sheetRef}
            initial={{ y: '100%', opacity: 0.8 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: '100%', opacity: 0 }}
            transition={{ type: 'spring', stiffness: 380, damping: 32 }}
            className={`w-full ${maxWidth} bg-bg-2 border apple-border rounded-t-sheet sm:rounded-sheet shadow-2xl overflow-hidden flex flex-col max-h-[85vh] focus:outline-none`}
            tabIndex={-1}
          >
            {/* Grab handle for mobile */}
            <div className="w-12 h-1 bg-fill rounded-full mx-auto mt-2.5 sm:hidden" />

            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b apple-border">
              <h3 className="text-base font-semibold text-label">{title}</h3>
              <button
                type="button"
                onClick={onClose}
                className="w-8 h-8 rounded-full bg-fill/50 hover:bg-fill flex items-center justify-center text-label-2 hover:text-label transition-colors focus:outline-none focus:ring-2 focus:ring-blue"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content body */}
            <div className="p-5 overflow-y-auto flex-1">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
