import React from 'react';
import { useLanguage } from '../../contexts/LanguageContext';

const LanguageSelector = ({ variant = 'dropdown', className = '' }) => {
  const { currentLanguage, changeLanguage, availableLanguages, isChanging } = useLanguage();

  if (variant === 'buttons') {
    return (
      <div className={`flex space-x-2 ${className}`}>
        {availableLanguages.map((lang) => (
          <button
            key={lang.code}
            onClick={() => changeLanguage(lang.code)}
            disabled={isChanging || currentLanguage === lang.code}
            className={`px-3 py-1 rounded-[2px] border text-sm font-medium transition-colors ${
              currentLanguage === lang.code
                ? 'bg-[color:var(--accent)] border-[color:var(--accent)] text-[color:var(--white)]'
                : 'bg-[color:var(--bg-secondary)] border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
            type="button"
          >
            {lang.flag} {lang.name}
          </button>
        ))}
      </div>
    );
  }

  // Dropdown variant (default)
  return (
    <select
      value={currentLanguage}
      onChange={(e) => changeLanguage(e.target.value)}
      disabled={isChanging}
      className={`px-3 py-1 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] text-sm text-[color:var(--text-primary)] focus:outline-none focus:border-[color:var(--accent)] ${className} ${
        isChanging ? 'opacity-50 cursor-not-allowed' : ''
      }`}
    >
      {availableLanguages.map((lang) => (
        <option key={lang.code} value={lang.code}>
          {lang.flag} {lang.name}
        </option>
      ))}
    </select>
  );
};

export default LanguageSelector;
