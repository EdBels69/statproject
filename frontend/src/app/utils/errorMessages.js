export const errorMessages = [
  {
    re: /could not convert string to float|cannot convert|invalid literal for int|could not convert|invalid input syntax/i,
    title: 'В данных есть текст там, где ожидаются числа',
    actions: [
      'Выберите числовую переменную для Target/Outcome.',
      'На шаге подготовки данных преобразуйте колонку в числа или уберите текстовые значения.',
    ],
  },
  {
    re: /KeyError|column.*not found|not in index|unknown column|no such column/i,
    title: 'Колонка не найдена в данных',
    actions: [
      'Проверьте, что колонка существует и не была переименована.',
      'Выберите переменные заново в Workspace.',
    ],
  },
  {
    re: /singular matrix|LinAlgError|nan.*infs?|perfect separation|SVD did not converge/i,
    title: 'Модель не может быть оценена на этих данных',
    actions: [
      'Проверьте, что в данных есть вариативность (нет константных колонок).',
      'Уберите лишние ковариаты или коллинеарные признаки.',
      'Если это логистическая регрессия — проверьте, что классы не разделяются идеально.',
    ],
  },
  {
    re: /not enough data|at least|insufficient|too few|requires at least/i,
    title: 'Недостаточно данных для выбранного метода',
    actions: [
      'Проверьте размер выборки и баланс по группам.',
      'Упростите модель или выберите другой тест.',
    ],
  },
  {
    re: /shapiro|normality|levene|homogeneity|assumption/i,
    title: 'Нарушены статистические предпосылки',
    actions: [
      'Попробуйте непараметрический тест или трансформацию данных.',
      'Проверьте выбросы и пропуски.',
    ],
  },
  {
    re: /division by zero|zero division/i,
    title: 'Деление на ноль при расчёте',
    actions: [
      'Проверьте, что выбранная переменная не константная.',
      'Убедитесь, что в данных есть ненулевые значения и вариативность.',
    ],
  },
  {
    re: /timeout|timed out/i,
    title: 'Анализ выполняется слишком долго',
    actions: [
      'Упростите протокол: меньше ковариат, меньше шагов.',
      'Попробуйте запустить анализ ещё раз.',
    ],
  },
];

export function parseError(raw) {
  const text = String(raw || '').trim();
  if (!text) {
    return {
      title: 'Неизвестная ошибка',
      details: '',
      actions: ['Попробуйте запустить анализ ещё раз.', 'Если ошибка повторяется — проверьте выбранные переменные.'],
    };
  }

  const hit = errorMessages.find((p) => p.re.test(text));
  if (!hit) {
    return {
      title: 'Ошибка выполнения анализа',
      details: text,
      actions: ['Проверьте настройки теста и выбранные переменные.', 'Если не помогает — попробуйте другой тест или шаблон.'],
    };
  }

  return {
    title: hit.title,
    details: text,
    actions: hit.actions,
  };
}
