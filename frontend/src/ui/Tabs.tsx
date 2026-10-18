import { motion } from 'framer-motion';

export interface TabItem<T extends string> {
  id: T;
  label: string;
  badge?: number | string;
}

export interface TabsProps<T extends string> {
  tabs: TabItem<T>[];
  activeTab: T;
  onChange: (id: T) => void;
  className?: string;
  name?: string;
}

export function Tabs<T extends string>({
  tabs,
  activeTab,
  onChange,
  className = '',
  name = 'apple-tabs',
}: TabsProps<T>) {
  return (
    <div className={`flex border-b apple-border px-2 select-none ${className}`}>
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`relative py-3 px-4 text-xs font-semibold flex items-center space-x-1.5 focus:outline-none transition-colors min-h-[44px] ${
              isActive ? 'text-blue' : 'text-label-2 hover:text-label'
            }`}
          >
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                  isActive ? 'bg-blue text-white' : 'bg-fill text-label-2'
                }`}
              >
                {tab.badge}
              </span>
            )}
            {isActive && (
              <motion.div
                layoutId={`tab-underline-${name}`}
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue rounded-full"
                transition={{ type: 'spring', stiffness: 500, damping: 35 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
