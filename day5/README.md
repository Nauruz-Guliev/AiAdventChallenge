# День 5 — Слабая, средняя и сильная модель

Один и тот же аналитический запрос отправляется трём моделям через OpenCode Go. Модели предварительно выбраны по официальным карточкам Hugging Face, а OpenCode Go используется как единый OpenAI-compatible транспорт. Интерфейс показывает ответ, время API-вызова, usage-токены и расчётную стоимость.

## Модели

| Уровень эксперимента | Модель | Reference-тариф OpenCode Go, input / output за 1M токенов |
| --- | --- | --- |
| Слабая | [`deepseek-ai/DeepSeek-V4-Flash`](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) | `$0.22 / $0.66` |
| Средняя | [`zai-org/GLM-5.3-Flash`](https://huggingface.co/zai-org/GLM-5.3-Flash) | `$0.07 / $0.25` |
| Сильная | [`moonshotai/Kimi-K3`](https://huggingface.co/moonshotai/Kimi-K3) | `$3.00 / $15.00` |

HF-карточки и опубликованные характеристики являются основанием выбора. Ярлыки «слабая / средняя / сильная» — экспериментальный proxy, а не официальный общий рейтинг Hugging Face: разные leaderboard-метрики могут дать другой порядок. Каталог и тарифы могут измениться. Бесплатный `ox-alpha-free` был проверен отдельно, но этот API-ключ получил ответ `401 Model ox-alpha-free is not supported`, поэтому модель не включена в рабочий эксперимент.

## Что замеряется

- Время: длительность одного HTTP-вызова от сервера к модели.
- Токены: `prompt_tokens`, `completion_tokens` и `total_tokens` из ответа API.
- Стоимость: `(input tokens / 1M × input price) + (output tokens / 1M × output price)`.
- Качество: небольшая rubric-проверка ожидаемого портфеля и ключевых ограничений. Это вспомогательный сигнал, а смысловой вывод нужно делать чтением ответов.

OpenCode Go работает по подписке, поэтому показанная цена является расчётом по reference-тарифам каталога, а не отдельным списанием с аккаунта.

## Запуск

```bash
npm install
cp .env.example .env
```

В `.env` укажи ключ OpenCode Go:

```env
OPENAI_API_KEY=your_opencode_go_api_key_here
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
PORT=3005
```

Запуск:

```bash
npm start
```

Открой `http://localhost:3005`.

## Ссылки

- [OpenCode Go](https://opencode.ai/docs/go/)
- [OpenCode provider docs](https://opencode.ai/docs/providers/)
- [Каталог OpenCode Go и тарифы](https://models.dev/providers/opencode-go/)
- [GLM-5.3 Flash в каталоге OpenCode Go](https://models.dev/models/zhipuai/glm-5.3-flash)
- [DeepSeek V4 Flash в каталоге OpenCode Go](https://models.dev/models/deepseek/deepseek-v4-flash)
- [Kimi K3 в каталоге OpenCode Go](https://models.dev/models/moonshotai/kimi-k3)
