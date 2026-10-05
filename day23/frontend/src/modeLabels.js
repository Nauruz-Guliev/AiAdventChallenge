export const MODE_LABELS = [
  ['no_rag', 'Без RAG'],
  ['rag', 'RAG (baseline)'],
  ['rag_filter', 'RAG + фильтр/реранк'],
  ['rag_rewrite', 'RAG + rewrite'],
  ['rag_full', 'RAG + rewrite + фильтр'],
];

const LABELS = Object.fromEntries(MODE_LABELS);

export function modeLabel(mode) {
  return LABELS[mode] || mode;
}
