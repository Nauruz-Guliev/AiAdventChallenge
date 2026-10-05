# Источники корпуса (Kotlin Multiplatform)

Корпус собран скриптом [`fetch_docs.py`](./fetch_docs.py) в `corpus/` и зафиксирован в
репозитории как markdown, чтобы индексация была воспроизводимой. Актуальность — на
момент сборки.

## `corpus/kmp-docs/` — официальная документация KMP (122 файла)

Репозиторий: **`JetBrains/kotlin-multiplatform-dev-docs`** (branch `master`), папка
`topics/`. Это исходники документации Kotlin Multiplatform с kotlinlang.org и
JetBrains Help (Compose Multiplatform, разработка, инструменты, roadmap, whats-new).
Скачиваются все `topics/**/*.md`, кроме `topics/temp/`. Из текста удаляются служебные
Writeside-теги, заголовок берётся из `[//]: # (title: …)`.

Покрытие тем: обзор KMP и поддерживаемые платформы, структура проекта, `expect`/`actual`,
подключение платформенных API, зависимости, иерархия source set'ов, компиляции,
нативные бинарники, интеграция с iOS (Swift/ObjC, CocoaPods, SPM), публикация,
Compose Multiplatform (навигация, ресурсы, ViewModel, lifecycle, тесты, desktop, web),
инструменты (DSL reference, toolchain, IDE, CI), roadmap и релизы.

## `corpus/libs/` — README ключевых библиотек

| Библиотека | Источник |
|---|---|
| kotlinx.coroutines | `Kotlin/kotlinx.coroutines` (master) |
| kotlinx.serialization | `Kotlin/kotlinx.serialization` (master) |
| kotlinx-datetime | `Kotlin/kotlinx-datetime` (master) |
| kotlinx-io | `Kotlin/kotlinx-io` (master) |
| kotlinx-atomicfu | `Kotlin/kotlinx-atomicfu` (master) |
| Ktor | `ktorio/ktor` (main) + страница ktor.io |
| Compose Multiplatform | `JetBrains/compose-multiplatform` (master) |
| SQLDelight | `cashapp/sqldelight` (master) |
| Multiplatform Settings | `russhwolf/multiplatform-settings` (main) |
| MOKO MVVM / Resources | `icerockdev/moko-mvvm`, `icerockdev/moko-resources` |
| Koin | `InsertKoinIO/koin` (main) |
| Store | `dropbox/Store` (main) |

## `corpus/ru/` — официальные русские переводы

Источник: **`phplego/kotlinlang.ru`** (master) — русский перевод kotlinlang.org.
Взяты страницы по KMP: обзор, начало работы, DSL reference, добавление зависимостей,
Android/iOS onboarding, корутины.

## Объём

144 документа, ~1.8 млн символов (≈1000 страниц текста).
