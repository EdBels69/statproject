import Button from '../../components/ui/Button';

export default function ProtocolSorcererRecommendationCard({
  recommendation,
  showApplyForm,
  onReset,
  onOpenApplyForm,
}) {
  if (!recommendation) return null;

  return (
    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-10 text-center relative overflow-hidden">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-[2px] bg-[color:var(--bg-secondary)] text-[color:var(--accent)] mb-8 border border-[color:var(--border-color)]">
        <span className="text-4xl">💡</span>
      </div>
      <div className="text-[color:var(--text-secondary)] text-sm font-bold uppercase tracking-widest mb-2">Решение по протоколу</div>
      <h2 className="text-4xl font-black text-[color:var(--text-primary)] mb-6">{recommendation.name}</h2>
      <p className="text-xl text-[color:var(--text-secondary)] mb-10 max-w-2xl mx-auto leading-relaxed">{recommendation.description}</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10 max-w-xl mx-auto text-left">
        {recommendation.assumptions?.map((ass, i) => (
          <div key={i} className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)] bg-[color:var(--bg-secondary)] px-4 py-2 rounded-[2px] border border-[color:var(--border-color)]">
            <span className="text-[color:var(--accent)]">✓</span> {ass}
          </div>
        ))}
      </div>

      {!showApplyForm ? (
        <div className="flex justify-center flex-wrap gap-4">
          <Button variant="ghost" onClick={onReset} className="px-8">
            Начать заново
          </Button>
          {recommendation.method_id !== 'consult_statistician' && (
            <Button variant="primary" onClick={onOpenApplyForm} className="px-8">
              Применить к файлу данных →
            </Button>
          )}
        </div>
      ) : null}
    </div>
  );
}
