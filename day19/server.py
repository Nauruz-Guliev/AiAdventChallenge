from mcp.server import MCPServer

import pipeline as pipeline_mod
import search_api
import storage
import summarizer

mcp = MCPServer("compose")

MAX_SENTENCES = 10


@mcp.tool()
def search(query: str, limit: int = 5) -> dict:
    """Поиск статей в Википедии.

    Args:
        query: Поисковый запрос.
        limit: Число результатов от 1 до 10. По умолчанию 5.
    """
    try:
        return search_api.search(query, limit)
    except search_api.SearchError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool()
def summarize(text: str, sentences: int = 3) -> dict:
    """Экстрактивная суммаризация текста.

    Args:
        text: Исходный текст.
        sentences: Число предложений в саммари (1..10). По умолчанию 3.
    """
    sentences = max(1, min(MAX_SENTENCES, sentences))
    return summarizer.summarize(text, sentences)


@mcp.tool()
def save_to_file(content: str, path: str | None = None) -> dict:
    """Сохранить текст в файл.

    Args:
        content: Текст для сохранения.
        path: Путь к файлу. По умолчанию day19/out/<epoch>-note.md.
    """
    try:
        return storage.save_to_file(content, path)
    except storage.StorageError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool()
def pipeline(query: str, path: str | None = None, sentences: int = 3) -> dict:
    """Автоматический пайплайн: search -> summarize -> save_to_file.

    Args:
        query: Поисковый запрос.
        path: Путь для сохранения. По умолчанию day19/out/<epoch>-<query>.md.
        sentences: Число предложений в саммари (1..10). По умолчанию 3.
    """
    try:
        return pipeline_mod.run(query, path, sentences)
    except (search_api.SearchError, storage.StorageError) as exc:
        raise ValueError(str(exc)) from exc


if __name__ == "__main__":
    mcp.run()
