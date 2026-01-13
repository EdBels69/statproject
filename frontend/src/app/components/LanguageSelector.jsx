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
            className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
              currentLanguage === lang.code
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
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
      className={`px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${className} ${
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