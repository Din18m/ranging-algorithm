# Ранжирование конфигураций HTAP-систем

Репозиторий содержит программный прототип алгоритма RASH и научную статью, оформленную по LaTeX-шаблону НИТУ «МИСиС». Прототип проводит воспроизводимый синтетический эксперимент или микробенчмарк SQLite/DuckDB, рассчитывает веса критериев из профиля нагрузки и ранжирует конфигурации по SLO, Парето-слоям и устойчивости измерений.

## Запуск алгоритма

Требуется Python 3.11 или новее. Для синтетического эксперимента сторонние библиотеки не нужны.

```bash
PYTHONPATH=src python -m htap_ranker run \
  --profile examples/profiles/balanced.json \
  --candidates examples/candidates.json \
  --output-dir results/balanced \
  --repetitions 30 \
  --seed 20261031
```

Команда создаёт `measurements.json` с отдельными повторами и `ranking.csv` с итоговым порядком. Повторное ранжирование сохранённых или импортированных измерений выполняется отдельно:

```bash
PYTHONPATH=src python -m htap_ranker rank \
  --profile examples/profiles/balanced.json \
  --measurements results/balanced/measurements.json \
  --output results/balanced/ranking-repeated.csv
```

Запуск тестов:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

В `results/` сохранены демонстрационные прогоны для транзакционного, аналитического и сбалансированного профилей. Это результаты имитационной модели, а не измерения реальных СУБД. Формат `measurements.json` позволяет позднее подставить данные BenchBase или HATtrick.

## Микробенчмарк SQLite и DuckDB

Для натурного опыта установите необязательную зависимость DuckDB и запустите отдельную команду:

```bash
python -m pip install -e ".[benchmark]"
python -m htap_ranker benchmark \
  --profile examples/profiles/live_microbenchmark.json \
  --output-dir results/live \
  --rows 50000 \
  --oltp-operations 200 \
  --olap-queries 7 \
  --repetitions 7 \
  --seed 20261103
```

Команда сравнивает SQLite, DuckDB и простой разделённый контур SQLite+DuckDB. Она сохраняет сырые повторы в `measurements.json`, сведения о машине и версиях в `environment.json`, а итоговый порядок — в `ranking.csv`. Готовый анализ чувствительности лежит в `results/sensitivity.csv`.

Это показательный микробенчмарк, а не промышленный HTAP-тест: СУБД работают в памяти и без конкурентных клиентов, а перенос SQLite→DuckDB выполнен построчно на Python. Эти ограничения явно учтены в статье.

## BenchBase CH-benCHmark

Дополнительный эксперимент использует смешанную нагрузку BenchBase: TPC-C для OLTP и запросы CH-benCHmark для OLAP. Конфигурация PostgreSQL находится в `benchmarks/benchbase/postgres-chbenchmark.xml`, а точные команды и ограничения опыта описаны в `benchmarks/benchbase/README.md`.

В `results/benchbase/` сохранены три исходных CSV-файла BenchBase, служебные JSON-сводки, параметры окружения и итоговые медианы. Тест `tests/test_benchbase.py` заново вычисляет p99 OLTP, p95 OLAP и throughput из исходных файлов, поэтому GitHub Actions проверяет числа, использованные в статье.

BenchBase не измеряет свежесть реплики. Его результаты не преобразуются в полный балл RASH с выдуманным значением лага, а используются как отдельная проверка конкурентной OLTP- и OLAP-нагрузки. Для полной проверки свежести в статье оставлена методика HATtrick.

## Сборка статьи

```bash
make article
# PDF: build/article.pdf
```

Компилятор по умолчанию — Tectonic. В GitHub Actions сначала устанавливаются зависимости микробенчмарка и запускаются все тесты, затем статья собирается на Windows с Times New Roman и публикуется как артефакт.

## Исходный шаблон

Основа репозитория — шаблон научной статьи НИТУ «МИСиС» (LaTeX).

LaTeX-шаблон статьи для сборника НИТУ «МИСиС»: XeLaTeX, две колонки.  
Репозиторий: [sadekovlar/misis-article-latex](https://github.com/sadekovlar/misis-article-latex)

Шаблон воспроизводит оформление эталонной статьи. **Параметры вёрстки заданы в `misisarticle.cls`** — в `.tex`-файле остаётся текст и команды титула.

## Быстрый старт

1. Откройте `article.tex`.
2. Компилятор: **XeLaTeX** (локально подойдёт и tectonic).
3. Заполните коды, название, авторов, аннотацию и ключевые слова.

### Overleaf

В Overleaf загружайте не весь репозиторий, а архив без примера:

```bash
make dist
# → dist/misis-article.zip
```

1. New Project → Upload Project → `dist/misis-article.zip`.
2. Menu → Compiler → **XeLaTeX**.
3. Главный файл — `article.tex`. Заполните блоки и нажмите Recompile.

### Локально

```bash
# macOS: MacTeX, либо brew install tectonic
make article
# PDF: build/article.pdf

# либо прямо:
tectonic article.tex
xelatex article.tex && xelatex article.tex
```

Файл `misisarticle.cls` должен лежать рядом с вашим `.tex`.

## Что заполнить в `article.tex`

1. `\grnti{}`, `\asjc{}`, `\oecd{}` — коды, либо `{}`, если код не нужен.
2. `\title{}` — название.
3. `\misisauthor{ФИО}{кафедра}{город, страна}{email}` — на каждого автора. Первый попадает в левую колонку, остальные — в правую.
4. `\abstract{}` или `\setabstract{}`, `\keywords{}` или `\setkeywords{}`. Пары команд эквивалентны.
5. Разделы `\section{}`, `\subsection{}`, рисунки, таблицы и список `\begin{thebibliography}`.

Список литературы набирается вручную в `thebibliography`. Класс оформляет этот список сам.

### Минимальный пример

```latex
\documentclass{misisarticle}

\grnti{47.01.07, 47.01.09}
\asjc{1707, 2207}
\oecd{1020, 1070}

\title{Название статьи}

\misisauthor{И.~О.~Иванов}{кафедра ... НИТУ «МИСиС»}{Москва, Россия}{student@edu.misis.ru}
\misisauthor{П.~П.~Петров}{кафедра ... НИТУ «МИСиС»}{Москва, Россия}{student2@edu.misis.ru}

\setabstract{Текст аннотации...}
\setkeywords{ключевое слово 1, ключевое слово 2}

\begin{document}
\maketitle

\section{Введение}
Текст раздела...
\end{document}
```

## Файлы

| Файл | Назначение |
|------|------------|
| `article.tex` | Текст статьи |
| `misisarticle.cls` | Класс оформления |
| `example/` | Эталонная статья для проверки класса, в zip для Overleaf не входит |
| `Makefile` | `make article`, `make example`, `make dist` |

## Оформление

| Элемент | Параметры |
|---------|-----------|
| Формат | A4, **две колонки** (IEEE-style) |
| Поля | верх 1,9 см; низ 2,54 см; лево/право 1,57 см; зазор колонок 0,635 см |
| Шрифт | Times New Roman, **10 pt** (в двухколоночном режиме). Если шрифта нет, класс берёт TeX Gyre Termes |
| Переносы слов | **отключены** по всему документу |
| Абзацный отступ | 0,51 см |
| Классификация | `ГРНТИ …`, `ASJC …`, `OECD …` — подпись и коды **в одной строке** |
| Название | 24 pt, по центру, на всю ширину; после него — строка отступа |
| Авторы | 11 pt; невидимая таблица: **1-й слева, 2-й справа**, между колонками пустой зазор; внутри каждой ячейки текст **по центру** |
| Аннотация | **Аннотация —** текст (метка и текст **жирным**, в колонках) |
| Ключевые слова | **Ключевые слова —** текст (жирным) |
| Раздел | **I. ВВЕДЕНИЕ** — римские цифры, small caps, по центру |
| Подраздел | *A. LISA* — буквы A, B, C…, курсив |
| Подписи рисунков | «Рис. N.», мелкий шрифт |
| Подписи таблиц | «Таблица I.» (римские цифры) |
| Литература | заголовок **ЛИТЕРАТУРА** по центру; `[N]` и текст на одной строке, мелкий шрифт |

## Пример

Каталог `example/` — полная статья, по которой сверяется класс. Это не заготовка для новой работы.

```bash
make example
# готовый PDF для просмотра: example/build/example.pdf
```

Рядом с `example.tex` лежит ссылка `misisarticle.cls` на класс в корне, поэтому команда `\documentclass` такая же, как в шаблоне. PDF шаблона и примера можно скачать из артефактов [GitHub Actions](https://github.com/sadekovlar/misis-article-latex/actions): `article.pdf` и `example.pdf`.

## Чек-лист перед сдачей

- [ ] Компилятор: **XeLaTeX** (или tectonic)
- [ ] Файл `misisarticle.cls` рядом с вашим `.tex`
- [ ] Заполнены коды, аннотация и ключевые слова
- [ ] Рисунки с подписями «Рис. N.»
- [ ] Таблицы с подписями «Таблица …»
- [ ] PDF собирается без ошибок

## Лицензия

Класс `misisarticle.cls` распространяется под [LPPL 1.3c](https://www.latex-project.org/lppl/). Текст лицензии — в файле `LICENSE`.
