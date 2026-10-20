import ast
import csv
import os
from pathlib import Path
from src.scraper import Extractor, Scraper
from src.filters import title_filter, keywords_filter, abstract_filter

from loguru import logger
from pyprojroot import here

import traceback
from typing import Any, List


def modify_paper(paper):

    paper.forum = f"https://openreview.net/forum?id={paper.forum}"
    paper.content['pdf'] = f"https://openreview.net{paper.content['pdf']}"

    return paper

def get_papers_by_year(
    venues: List[str], 
    years: List[str], 
    keywords: List[str], 
    overwrite: bool = False, 
    fout: str = None
) -> bool:

    os.makedirs("outputs", exist_ok=True)

    fout = "outputs/papers.csv" if fout is None else f"outputs/{fout}"
    if os.path.exists(fout) and not overwrite:
        return False

    extractor = Extractor(
        fields=['forum'], 
        subfields={
            'content': [
                'title', 'keywords', 'abstract', 'pdf', 'match', 'reviews'
            ]
        }
    )

    ## manually select papers
    selector = None 
    scraper = Scraper(
        conferences=venues,
        years=years,
        keywords=keywords,
        extractor=extractor,
        fpath=fout,
        fns=[modify_paper],
        selector=selector
    )

    ## add_filters ##
    scraper.add_filter(keywords_filter)
    scraper.add_filter(title_filter)
    scraper.add_filter(abstract_filter)

    scraper()

    return True


def load_scrapped_papers(path: Path) -> List[dict[str, Any]]:
    """Load the CSV as a list with one dictionary per paper."""
    papers = []

    with path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):

            paper = {}
            for field, value in row.items():
                try:
                    parsed_value = ast.literal_eval(value)

                except (ValueError, SyntaxError, TypeError):
                    parsed_value = value

                if isinstance(parsed_value, dict) and "value" in parsed_value:
                    parsed_value = parsed_value["value"]

                paper[field] = parsed_value

            papers.append(paper)

    return papers


# , "NeurIPS", "ACL", "ICCV", "ICLR"
if __name__ == "__main__":

    scrap = False
    overwrite = True

    years = ['2026']
    conferences = ["ICML", "CVPR"]
    keywords = ["diffusion inverse problems"]
    out_fname = "representation.csv"

    if scrap: 

        try:

            out = get_papers_by_year(
                conferences, 
                years, 
                keywords, 
                overwrite=overwrite, 
                fout=out_fname
            )

            if not out:
                logger.info(f"--- out: {out}")

        except Exception as e:
            logger.info(f"traceback: \n {traceback.format_exc()}")
    
    else:
        output_path = Path(str(here())) / "outputs" / out_fname

        papers = load_scrapped_papers(output_path)
        logger.info("Loaded {} papers from {}", len(papers), output_path)
