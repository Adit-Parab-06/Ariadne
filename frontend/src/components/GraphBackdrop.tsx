import React from 'react';

export type GraphTheme = 'celestial' | 'radar' | 'obsidian' | 'classic';

interface GraphBackdropProps {
  theme: GraphTheme;
  isExpanded?: boolean;
}

export const GraphBackdrop: React.FC<GraphBackdropProps> = ({ theme, isExpanded = false }) => {
  if (theme === 'classic') {
    return <div className="absolute inset-0 bg-bg pointer-events-none transition-colors duration-300" />;
  }

  if (theme === 'obsidian') {
    return (
      <div className="absolute inset-0 bg-[#070709] pointer-events-none overflow-hidden transition-all duration-300">
        {/* Micro-dot constellation */}
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage: 'radial-gradient(rgba(255, 255, 255, 0.16) 1.2px, transparent 1.2px)',
            backgroundSize: '24px 24px',
          }}
        />
        {/* Deep edge vignette */}
        <div className="absolute inset-0 shadow-[inset_0_0_60px_rgba(0,0,0,0.85)]" />
      </div>
    );
  }

  if (theme === 'radar') {
    return (
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_#051c24_0%,_#021016_55%,_#010508_100%)] pointer-events-none overflow-hidden transition-all duration-300">
        {/* Tactical blueprint grid */}
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: `
              linear-gradient(rgba(48, 176, 199, 0.12) 1px, transparent 1px),
              linear-gradient(90deg, rgba(48, 176, 199, 0.12) 1px, transparent 1px)
            `,
            backgroundSize: '32px 32px',
          }}
        />

        {/* Concentric telemetry rings */}
        <svg className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <radialGradient id="radar-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#30b0c7" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#30b0c7" stopOpacity="0" />
            </radialGradient>
          </defs>
          <circle cx="50%" cy="50%" r={isExpanded ? 380 : 180} fill="none" stroke="#30b0c7" strokeWidth="1" strokeDasharray="3 6" opacity="0.25" />
          <circle cx="50%" cy="50%" r={isExpanded ? 240 : 110} fill="none" stroke="#30b0c7" strokeWidth="1" strokeDasharray="4 8" opacity="0.3" />
          <circle cx="50%" cy="50%" r={isExpanded ? 110 : 50} fill="none" stroke="#30b0c7" strokeWidth="1" opacity="0.35" />
          <circle cx="50%" cy="50%" r={isExpanded ? 70 : 30} fill="url(#radar-glow)" />

          {/* Crosshair axes */}
          <line x1="50%" y1="0%" x2="50%" y2="100%" stroke="#30b0c7" strokeWidth="0.75" strokeDasharray="2 6" opacity="0.2" />
          <line x1="0%" y1="50%" x2="100%" y2="50%" stroke="#30b0c7" strokeWidth="0.75" strokeDasharray="2 6" opacity="0.2" />

          {/* Rotating radar sweep */}
          <g className="animate-radar-sweep" style={{ transformOrigin: '50% 50%' }}>
            <line x1="50%" y1="50%" x2="50%" y2={isExpanded ? '10%' : '15%'} stroke="#30b0c7" strokeWidth="1.5" opacity="0.5" />
          </g>
        </svg>

        {/* Vignette */}
        <div className="absolute inset-0 shadow-[inset_0_0_60px_rgba(0,0,0,0.8)]" />
      </div>
    );
  }

  // Default: Celestial Nebula (The dynamic, illustrious cosmic design)
  return (
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_120%_120%_at_50%_0%,_#0e172e_0%,_#080e1d_45%,_#02050b_100%)] pointer-events-none overflow-hidden transition-all duration-300">
      {/* Dynamic Animated Ambient Nebula Orbs */}
      <div className="absolute -top-16 -left-16 w-80 h-80 rounded-full bg-[#0071e3]/20 blur-3xl animate-nebula pointer-events-none" />
      <div className="absolute -bottom-20 -right-20 w-96 h-96 rounded-full bg-[#af52de]/15 blur-3xl animate-nebula-reverse pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 rounded-full bg-[#30b0c7]/10 blur-3xl pointer-events-none" />

      {/* Star Matrix Dot Pattern */}
      <div
        className="absolute inset-0 opacity-45"
        style={{
          backgroundImage: 'radial-gradient(rgba(255, 255, 255, 0.16) 1.2px, transparent 1.2px)',
          backgroundSize: '26px 26px',
        }}
      />

      {/* Celestial Orbital Chart & Reticle */}
      <svg className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="nebula-center-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#0071e3" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#0071e3" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Center ambient pool */}
        <circle cx="50%" cy="50%" r={isExpanded ? 320 : 150} fill="url(#nebula-center-glow)" />

        {/* Orbital Range Rings */}
        <circle
          cx="50%"
          cy="50%"
          r={isExpanded ? 420 : 200}
          fill="none"
          stroke="rgba(255, 255, 255, 0.05)"
          strokeWidth="1"
          strokeDasharray="4 8"
        />
        <circle
          cx="50%"
          cy="50%"
          r={isExpanded ? 260 : 120}
          fill="none"
          stroke="rgba(255, 255, 255, 0.07)"
          strokeWidth="1"
          strokeDasharray="6 6"
        />
        <circle
          cx="50%"
          cy="50%"
          r={isExpanded ? 110 : 55}
          fill="none"
          stroke="rgba(255, 255, 255, 0.10)"
          strokeWidth="1"
        />

        {/* Precision Crosshair Center Reticle */}
        <line x1="50%" y1="46%" x2="50%" y2="54%" stroke="rgba(255, 255, 255, 0.18)" strokeWidth="1" />
        <line x1="48%" y1="50%" x2="52%" y2="50%" stroke="rgba(255, 255, 255, 0.18)" strokeWidth="1" />

        {/* Corner Precision Tech Brackets */}
        <g stroke="rgba(255, 255, 255, 0.14)" strokeWidth="1.2" fill="none">
          {/* Top-Left */}
          <path d="M 12 24 L 12 12 L 24 12" />
          {/* Top-Right */}
          <path d="M calc(100% - 24px) 12 L calc(100% - 12px) 12 L calc(100% - 12px) 24" />
          {/* Bottom-Left */}
          <path d="M 12 calc(100% - 24px) L 12 calc(100% - 12px) L 24 calc(100% - 12px)" />
          {/* Bottom-Right */}
          <path d="M calc(100% - 24px) calc(100% - 12px) L calc(100% - 12px) calc(100% - 12px) L calc(100% - 12px) calc(100% - 24px)" />
        </g>
      </svg>

      {/* Depth Vignette for edge absorption */}
      <div className="absolute inset-0 shadow-[inset_0_0_70px_rgba(0,0,0,0.85)]" />
    </div>
  );
};
