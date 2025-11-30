<div align="center">

# 🌸 WWM Translator

### Neural Translation Tool for Where Winds Meet

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-Powered-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-Compatible-6366F1?style=for-the-badge)](https://openrouter.ai)

[English](#-english) • [Русский](#-русский)

<img src="https://img.shields.io/badge/Where_Winds_Meet-逆水寒-CD7F32?style=for-the-badge" alt="Where Winds Meet"/>

</div>

---

# 🇬🇧 English

## 📖 About

**WWM Translator** is a professional-grade neural machine translation tool specifically designed for localizing the game **"Where Winds Meet"** (逆水寒). Powered by modern LLMs through LangChain, it provides high-quality translations while preserving the poetic essence and cultural nuances of the original Chinese text.

The tool extracts texts from the game's proprietary HashMap-based binary localization files, translates them using advanced AI models (supporting OpenRouter, OpenAI, Anthropic, and Google), and patches them back into the game — all while maintaining full structural integrity.

## ✨ Features

<table>
<tr>
<td width="50%">

### 🚀 Performance
- **Async batch processing** with configurable parallelism
- **Smart resume system** — never lose progress
- **Token-aware batching** for optimal LLM usage
- **Rate limiting** with exponential backoff

</td>
<td width="50%">

### 🎯 Quality
- **Context-aware translation** with surrounding lines
- **Multi-language context** (English + Chinese reference)
- **Special character validation** ensures formatting integrity
- **Length optimization** — avoids overly long translations

</td>
</tr>
<tr>
<td width="50%">

### 🔧 Technical
- **HashMap format support** — exact game format preservation
- **ZSTD compression** for game archives
- **Graceful shutdown** — Ctrl+C saves progress
- **Detailed logging** with Rich console output

</td>
<td width="50%">

### 📊 Analytics
- **Real-time ETA** calculation
- **Token counting** with cost estimation
- **Progress tracking** with visual progress bars
- **Verbose mode** for debugging

</td>
</tr>
</table>

## 🛠 Installation

### Prerequisites
- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Quick Start

```bash
# Clone the repository
git clone https://github.com/0niel/wwm_translator.git
cd wwm_translator

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Configuration

1. **Create `.env` file** with your API credentials:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
LLM_MODEL=deepseek/deepseek-chat-v3-0324

# Optional: Cost tracking
INPUT_PRICE_PER_MILLION=0.14
OUTPUT_PRICE_PER_MILLION=0.28
```

2. **Update `config.yaml`** with your game path:

```yaml
paths:
  game_locale_dir: "Y:/SteamLibrary/steamapps/common/Where Winds Meet/Package/HD/oversea/locale"

languages:
  source: "en"      # Translate from English
  target: "ru"      # To Russian
  patch_lang: "de"  # Replace German locale in-game
```

## 📋 Usage

### Complete Workflow

```bash
# 1. Extract texts from game files
python main.py extract en      # English texts
python main.py extract zh_cn   # Chinese texts (for context)

# 2. Run translation
python main.py translate       # Start translation
python main.py translate -V    # Verbose mode (see batches)

# 3. Check progress
python main.py status          # View translation status

# 4. Validate translations
python main.py validate        # Check special characters
python main.py validate --fix  # Mark issues for re-translation

# 5. Patch game files
python main.py autopatch              # Create patched files
python main.py autopatch --install    # Install to game folder
```

### Available Commands

| Command | Description |
|---------|-------------|
| `extract <lang>` | Extract texts from game locale files |
| `translate` | Start/resume translation process |
| `status` | Show translation progress and statistics |
| `validate` | Validate special characters in translations |
| `autopatch` | Create and optionally install patched files |
| `reset` | Reset all translation progress |
| `info` | Show locale files information |

### Command Options

```bash
# Translation with options
python main.py translate --verbose        # Show batch details
python main.py translate --batch-size 20  # Custom batch size

# Autopatch with options
python main.py autopatch --install        # Install to game
python main.py autopatch --with-diff      # Include diff files
```

## 📁 Project Structure

```
wwm_translator/
├── main.py                 # CLI entry point
├── config.yaml             # Main configuration
├── .env                    # API keys and secrets
├── pyproject.toml          # Project metadata & dependencies
│
├── src/                    # Source code
│   ├── config.py           # Configuration loading
│   ├── extractor.py        # Game file extraction
│   ├── hashmap_format.py   # HashMap binary format handling
│   ├── batch_processor.py  # Async batch translation
│   ├── llm_client.py       # LangChain LLM integration
│   ├── tokenizer.py        # Token counting & cost estimation
│   ├── models.py           # Data models
│   └── utils.py            # Utilities & logging
│
├── rules/                  # Translation rules
│   └── game_context.txt    # Game description for LLM context
│
├── data/                   # Working data (gitignored)
│   ├── source/             # Extracted source files
│   ├── translated/         # Translation results
│   └── progress/           # Progress checkpoints
│
└── logs/                   # Log files
```

## ⚙️ Configuration Reference

### LLM Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `provider` | `openrouter` | LLM provider (openrouter/openai/anthropic/google) |
| `model` | `deepseek/deepseek-chat-v3-0324` | Model identifier |
| `temperature` | `0.3` | Response randomness (0-1) |
| `max_tokens` | `4096` | Max tokens per response |

### Batch Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `size` | `10` | Texts per batch |
| `concurrent_requests` | `15` | Parallel API calls |
| `max_tokens_per_batch` | `4000` | Token limit per batch |
| `delay_between_batches` | `0.3` | Rate limiting delay |

## 🎮 Supported Models

| Provider | Models | Notes |
|----------|--------|-------|
| **OpenRouter** | DeepSeek, Grok, Claude, GPT-4, etc. | Recommended for variety |
| **OpenAI** | GPT-4o, GPT-4-turbo | Direct API access |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus | Excellent for nuanced text |
| **Google** | Gemini Pro, Gemini Ultra | Good balance |

---

# 🇷🇺 Русский

## 📖 О проекте

**WWM Translator** — профессиональный инструмент нейронного машинного перевода, специально разработанный для локализации игры **«Where Winds Meet»** (逆水寒, «Против течения»). Используя современные LLM через LangChain, инструмент обеспечивает высококачественный перевод, сохраняя поэтическую суть и культурные нюансы оригинального китайского текста.

Инструмент извлекает тексты из проприетарных бинарных файлов локализации игры (формат HashMap), переводит их с помощью продвинутых ИИ-моделей (OpenRouter, OpenAI, Anthropic, Google) и внедряет обратно в игру — сохраняя полную структурную целостность.

## ✨ Возможности

<table>
<tr>
<td width="50%">

### 🚀 Производительность
- **Асинхронная пакетная обработка** с настраиваемым параллелизмом
- **Умная система возобновления** — прогресс никогда не теряется
- **Учёт токенов** для оптимального использования LLM
- **Ограничение запросов** с экспоненциальной задержкой

</td>
<td width="50%">

### 🎯 Качество
- **Контекстно-зависимый перевод** с окружающими строками
- **Мультиязычный контекст** (английский + китайский)
- **Валидация спецсимволов** для сохранения форматирования
- **Оптимизация длины** — избегание слишком длинных переводов

</td>
</tr>
<tr>
<td width="50%">

### 🔧 Технические
- **Поддержка HashMap формата** — точное сохранение формата игры
- **ZSTD сжатие** для архивов игры
- **Корректное завершение** — Ctrl+C сохраняет прогресс
- **Подробное логирование** с Rich-выводом в консоль

</td>
<td width="50%">

### 📊 Аналитика
- **Расчёт ETA** в реальном времени
- **Подсчёт токенов** с оценкой стоимости
- **Отслеживание прогресса** с визуальными индикаторами
- **Verbose-режим** для отладки

</td>
</tr>
</table>

## 🛠 Установка

### Требования
- Python 3.11 или выше
- [uv](https://github.com/astral-sh/uv) (рекомендуется) или pip

### Быстрый старт

```bash
# Клонировать репозиторий
git clone https://github.com/0niel/wwm_translator.git
cd wwm_translator

# Установка через uv (рекомендуется)
uv sync

# Или через pip
pip install -e .
```

### Настройка

1. **Создайте файл `.env`** с вашими API-ключами:

```env
OPENROUTER_API_KEY=sk-or-v1-ваш-ключ
LLM_MODEL=deepseek/deepseek-chat-v3-0324

# Опционально: отслеживание стоимости
INPUT_PRICE_PER_MILLION=0.14
OUTPUT_PRICE_PER_MILLION=0.28
```

2. **Обновите `config.yaml`** с путём к игре:

```yaml
paths:
  game_locale_dir: "Y:/SteamLibrary/steamapps/common/Where Winds Meet/Package/HD/oversea/locale"

languages:
  source: "en"      # Переводим с английского
  target: "ru"      # На русский
  patch_lang: "de"  # Заменяем немецкую локаль в игре
```

## 📋 Использование

### Полный рабочий процесс

```bash
# 1. Извлечь тексты из файлов игры
python main.py extract en      # Английские тексты
python main.py extract zh_cn   # Китайские тексты (для контекста)

# 2. Запустить перевод
python main.py translate       # Начать перевод
python main.py translate -V    # Verbose-режим (показывать батчи)

# 3. Проверить прогресс
python main.py status          # Показать статус перевода

# 4. Валидировать переводы
python main.py validate        # Проверить спецсимволы
python main.py validate --fix  # Отметить проблемные для перевода

# 5. Патчить файлы игры
python main.py autopatch              # Создать запатченные файлы
python main.py autopatch --install    # Установить в папку игры
```

### Доступные команды

| Команда | Описание |
|---------|----------|
| `extract <lang>` | Извлечь тексты из файлов локализации |
| `translate` | Начать/возобновить процесс перевода |
| `status` | Показать прогресс и статистику |
| `validate` | Проверить спецсимволы в переводах |
| `autopatch` | Создать и установить патч |
| `reset` | Сбросить весь прогресс перевода |
| `info` | Показать информацию о файлах локализации |

### Опции команд

```bash
# Перевод с опциями
python main.py translate --verbose        # Показывать детали батчей
python main.py translate --batch-size 20  # Свой размер батча

# Патч с опциями
python main.py autopatch --install        # Установить в игру
python main.py autopatch --with-diff      # Включить diff-файлы
```

## 🎮 Поддерживаемые модели

| Провайдер | Модели | Примечания |
|-----------|--------|------------|
| **OpenRouter** | DeepSeek, Grok, Claude, GPT-4 и др. | Рекомендуется для разнообразия |
| **OpenAI** | GPT-4o, GPT-4-turbo | Прямой доступ к API |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus | Отлично для нюансированного текста |
| **Google** | Gemini Pro, Gemini Ultra | Хороший баланс |

## 🎮 Об игре

**Where Winds Meet** (逆水寒, дословно «Против течения») — масштабная китайская MMORPG от NetEase в жанре уся (武俠), действие которой разворачивается в древнем Китае эпохи Северной Сун (960-1127 н.э.). Игра сочетает глубокий сюжет, боевые искусства, исследование открытого мира и богатую систему крафта.

Игроки погружаются в детективный сюжет, расследуя загадочные исчезновения в атмосфере интриг императорского двора, предательств и древних тайн. Мир игры отличается потрясающей графикой, реалистичной физикой и вниманием к историческим деталям.

---

<div align="center">

## 📄 Лицензия / License

MIT License © 2025 [0niel](https://github.com/0niel)

---

Made with ❤️ for the Where Winds Meet community

**[⬆ Back to top](#-wwm-translator)**

</div>

