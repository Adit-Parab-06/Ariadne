import { motion } from 'framer-motion';

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string> {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  name?: string;
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  className = '',
  name = 'segmented-control',
}: SegmentedControlProps<T>) {
  return (
    <div
      role="radiogroup"
      className={`inline-flex items-center p-1 bg-fill rounded-xl relative select-none ${className}`}
    >
      {options.map((opt) => {
        const isSelected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={isSelected}
            onClick={() => onChange(opt.value)}
            className={`relative z-10 px-3 py-1 text-xs font-semibold rounded-lg transition-colors min-h-[36px] flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-blue ${
              isSelected ? 'text-label' : 'text-label-2 hover:text-label'
            }`}
          >
            {isSelected && (
              <motion.div
                layoutId={`segment-pill-${name}`}
                className="absolute inset-0 bg-bg rounded-lg shadow-sm -z-10"
                transition={{ type: 'spring', stiffness: 450, damping: 35 }}
              />
            )}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
