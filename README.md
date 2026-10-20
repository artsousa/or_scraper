# OpenReview Scraper
Scrape papers from top conferences like ICML, ICLR, NeurIPS, etc using OpenReview API, by searching for specific keywords in title, abstract or keywords in the submissions and save them to a CSV file.<br>
Brings down the time taken to gather papers from several hours to a few minutes through automation

## Installation
```python
git clone https://github.com/pranftw/openreview_scraper.git # clone repo
python -m venv venv # create virtual environment
source venv/bin/activate # activate virtual environment
pip install -r requirements.txt # install requirements
cp config.py.example config.py # enter your OpenReview credentials in config.py
```

## Run

Edit the conferences, years, keywords, and output filename in `run.py`, then run:

```bash
python run.py
```

Results are saved in `outputs/`. By default, only accepted papers are retrieved.

## Code layout

- `run.py`: search settings and the `get_papers_by_year` entry point.
- `src/scraper.py`: API clients, venue and paper retrieval, official review replies, extraction, optional manual selection, and CSV/pickle storage.
- `src/filters.py`: keyword matching against titles, abstracts, and paper keywords.
- `config.py`: local OpenReview credentials (copy from `config.py.example`).

## Use from Python

```python
from run import get_papers_by_year

get_papers_by_year(
    venues=["ICLR"],
    years=["2025"],
    keywords=["generalization"],
    fout="generalization.csv",
)
```

For custom pipelines, import `Scraper`, `Extractor`, `Selector`, `save_papers`,
and `load_papers` from `src.scraper`. Filters remain available from `src.filters`.
Each exported paper includes a `reviews` field with the visible official review
content and signatures returned by OpenReview.
