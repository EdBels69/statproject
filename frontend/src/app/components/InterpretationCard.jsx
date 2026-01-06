import React from 'react';
import { LightBulbIcon } from '@heroicons/react/24/outline';

const InterpretationCard = ({ pValue, methodId, effectSize }) => {
    if (pValue === null || pValue === undefined) return null;

    const isSig = pValue < 0.05;

    let title = isSig ? "Статистически значимые различия" : "Различия не обнаружены";
    let desc = isSig
        ? `P-значение (${pValue < 0.001 ? '<0.001' : pValue.toFixed(4)}) меньше 0.05, что позволяет отклонить нулевую гипотезу.`
        : `P-значение (${pValue.toFixed(4)}) больше 0.05. Нулевая гипотеза не может быть отклонена.`;

    // Method specific nuances
    if (methodId && methodId.includes("corr")) {
        title = isSig ? "Значимая корреляция" : "Корреляция не значима";
        desc = isSig
            ? `Обнаружена статистически надежная связь между переменными (p < 0.05).`
            : `Связь между переменными не подтверждена статистически.`;
    }

    // Effect Size Interpretation (Cohen's d mostly)
    let effectDesc = "";
    if (effectSize !== null && effectSize !== undefined && !methodId?.includes("corr")) {
        const absE = Math.abs(effectSize);
        let magnitude = "незначительный";
        if (absE >= 0.8) magnitude = "большой";
        else if (absE >= 0.5) magnitude = "средний";
        else if (absE >= 0.2) magnitude = "малый";

        effectDesc = ` Размер эффекта (Cohen's d = ${absE.toFixed(2)}) оценивается как ${magnitude}.`;
    }

    return (
        <div className={`rounded-xl p-5 border-l-4 mb-6 shadow-sm ${isSig ? 'bg-green-50 border-green-500' : 'bg-gray-50 border-gray-400'
            }`}>
            <div className="flex items-start">
                <LightBulbIcon className={`w-6 h-6 mr-3 ${isSig ? 'text-green-600' : 'text-gray-500'
                    }`} />
                <div>
                    <h4 className={`text-lg font-semibold ${isSig ? 'text-green-800' : 'text-gray-800'
                        }`}>
                        {title}
                    </h4>
                    <p className={`text-md mt-1 ${isSig ? 'text-green-700' : 'text-gray-600'
                        }`}>
                        {desc} {effectDesc}
                    </p>
                </div>
            </div>
        </div>
    );
};

export default InterpretationCard;
