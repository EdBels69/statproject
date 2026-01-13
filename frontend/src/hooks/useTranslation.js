import { useTranslation as useI18nTranslation } from 'react-i18next';

// Custom hook with additional functionality
export const useTranslation = () => {
  const { t, i18n, ready } = useI18nTranslation();
  
  // Format numbers according to current locale
  const formatNumber = (number, options = {}) => {
    return new Intl.NumberFormat(i18n.language, options).format(number);
  };
  
  // Format dates according to current locale
  const formatDate = (date, options = {}) => {
    return new Intl.DateTimeFormat(i18n.language, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      ...options
    }).format(new Date(date));
  };
  
  // Get current language
  const currentLanguage = i18n.language;
  
  // Change language
  const changeLanguage = (lng) => {
    i18n.changeLanguage(lng);
    localStorage.setItem('preferredLanguage', lng);
  };
  
  // Check if translation is available
  const hasTranslation = (key) => {
    return i18n.exists(key);
  };
  
  return {
    t,
    i18n,
    ready,
    formatNumber,
    formatDate,
    currentLanguage,
    changeLanguage,
    hasTranslation,
    // Shortcut methods for common translations
    translate: t,
    isRussian: currentLanguage === 'ru',
    isEnglish: currentLanguage === 'en'
  };
};