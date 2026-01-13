import React, { createContext, useContext, useEffect, useState } from 'react';
import { useTranslation } from '../hooks/useTranslation';

const LanguageContext = createContext();

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};

export const LanguageProvider = ({ children }) => {
  const translation = useTranslation();
  const [isChanging, setIsChanging] = useState(false);

  // Initialize language from localStorage or browser preference
  useEffect(() => {
    const savedLanguage = localStorage.getItem('preferredLanguage');
    const browserLanguage = navigator.language.startsWith('ru') ? 'ru' : 'en';
    
    if (savedLanguage && ['ru', 'en'].includes(savedLanguage)) {
      translation.changeLanguage(savedLanguage);
    } else if (browserLanguage === 'ru') {
      translation.changeLanguage('ru');
    }
  }, [translation]);

  const changeLanguage = async (lng) => {
    if (!['ru', 'en'].includes(lng)) return;
    
    setIsChanging(true);
    try {
      await translation.changeLanguage(lng);
      localStorage.setItem('preferredLanguage', lng);
    } catch (error) {
      console.error('Failed to change language:', error);
    } finally {
      setIsChanging(false);
    }
  };

  const value = {
    ...translation,
    isChanging,
    changeLanguage,
    availableLanguages: [
      { code: 'ru', name: 'Русский', flag: '🇷🇺' },
      { code: 'en', name: 'English', flag: '🇺🇸' }
    ]
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};
