export const MODE_LABELS = [
  ['no_rag', 'Без RAG'],
  ['rag', 'RAG + цитаты'],
  ['rag_guard', 'RAG Guard (цитаты + «не знаю»)'],
];

const LABELS = Object.fromEntries(MODE_LABELS);

export function modeLabel(mode) {
  return LABELS[mode] || mode;
}
