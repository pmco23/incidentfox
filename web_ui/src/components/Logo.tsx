import React from 'react';
import Image from 'next/image';

export const Logo = ({ className = "w-8 h-8" }: { className?: string }) => (
  <div className={`relative ${className}`}>
    <Image 
        src="/logo.png" 
        alt="IncidentFox Logo" 
        fill
        className="object-contain"
    />
  </div>
);

export const LogoFull = () => (
    <div className="flex items-center gap-3">
        <div className="relative w-10 h-10 flex-shrink-0">
             <Image 
                src="/logo.png" 
                alt="IncidentFox" 
                fill
                className="object-contain"
            />
        </div>
        <span className="font-bold text-xl tracking-tight text-gray-900 dark:text-white">
            Incident<span className="text-orange-600">Fox</span>
        </span>
    </div>
);
