import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
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
  const [educationLevel, setEducationLevel] = useState('junior');
  const isInitialized = useRef(false);

  // Initialize language from localStorage or browser preference (only once)
  useEffect(() => {
    if (isInitialized.current) return;
    isInitialized.current = true;

    const savedLanguage = localStorage.getItem('preferredLanguage');
    const browserLanguage = navigator.language.startsWith('ru') ? 'ru' : 'en';

    const savedLevel = localStorage.getItem('statwizard_education_level');
    if (savedLevel && ['junior', 'mid', 'senior'].includes(savedLevel)) {
      setEducationLevel(savedLevel);
    }

    if (savedLanguage && ['ru', 'en'].includes(savedLanguage)) {
      translation.i18n.changeLanguage(savedLanguage);
    } else if (browserLanguage === 'ru') {
      translation.i18n.changeLanguage('ru');
    }
  }, [translation.i18n]);

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

  const changeEducationLevel = (nextLevel) => {
    if (!['junior', 'mid', 'senior'].includes(nextLevel)) return;
    setEducationLevel(nextLevel);
    try {
      localStorage.setItem('statwizard_education_level', nextLevel);
    } catch {
      void 0;
    }
  };

  const value = {
    ...translation,
    isChanging,
    changeLanguage,
    educationLevel,
    changeEducationLevel,
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
