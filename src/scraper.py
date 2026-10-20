"""OpenReview clients, paper retrieval, processing, and export."""

import csv
import os

import dill
import openreview

from config import EMAIL, PASSWORD
from .filters import satisfies_any_filters


def get_client():
    """
    Returns a tuple of (client_v1, client_v2) for both OpenReview API versions.
    """

    client_v1 = openreview.Client(
        baseurl='https://api.openreview.net',
        username=EMAIL,
        password=PASSWORD
    )

    client_v2 = openreview.api.OpenReviewClient(
        baseurl='https://api2.openreview.net',
        username=EMAIL,
        password=PASSWORD
    )

    return client_v1, client_v2


def papers_to_list(papers):
    all_papers = []
    for grouped_venues in papers.values():
        for venue_papers in grouped_venues.values():
            for paper in venue_papers:
                all_papers.append(paper)
    return all_papers


def to_csv(papers_list, fpath):
    def write_csv():
        with open(fpath, 'a+') as fp:
            fp.seek(0, 0) # seek to beginning of file and then read
            previous_contents = fp.read()
            writer = csv.DictWriter(fp, fieldnames=field_names)
            if previous_contents.strip()=='':
                writer.writeheader()
            writer.writerows(papers_list)
    if len(papers_list)>0:
        field_names = list(papers_list[0].keys()) # choose one of the papers, get all the keys as they'll be same for rest of them
        write_csv()


def save_papers(papers, fpath):
    with open(fpath, 'wb') as fp:
        dill.dump(papers, fp)
        print(f'Papers saved at: {fpath}')


def load_papers(fpath):
    with open(fpath, 'rb') as fp:
        papers = dill.load(fp)
    print(f'Papers loaded from: {fpath}')
    return papers


def get_venues(clients, confs, years):
    """
    Get venues from both API v1 and API v2 clients and merge the results.

    Args:
        clients: Tuple of (client_v1, client_v2)
        confs: List of conference names
        years: List of years

    Returns:
        List of venue IDs
    """
    client_v1, client_v2 = clients

    def filter_year(venue):
        if venue is None:
            return None
        for year in years:
            if year in venue:
                return venue
        return None

    # Get venues from API v1
    venues_v1 = []
    try:
        venues_v1 = client_v1.get_group(id='venues').members
    except Exception as e:
        print(f"Error getting venues from API v1: {e}")

    # Get venues from API v2
    venues_v2 = []
    try:
        venues_v2 = client_v2.get_group(id='venues').members
    except Exception as e:
        print(f"Error getting venues from API v2: {e}")

    # Merge venues from both APIs
    venues = list(set(venues_v1 + venues_v2))

    venues = list(map(filter_year, venues))
    venues = filter(lambda venue: venue is not None, venues)

    reqd_venues = []
    for venue in venues:
        for conf in confs:
            if conf.lower() in venue.lower():
                reqd_venues.append(venue)
                break
    
    reqd_venues = map(filter_year, reqd_venues)
    reqd_venues = list(filter(lambda venue: venue is not None, reqd_venues))

    return reqd_venues


def group_venues(venues, bins):
    def get_bins_dict():
        bins_dict = {bin:[] for bin in bins}
        return bins_dict

    bins_dict = get_bins_dict()
    for venue in venues:
        for bin in bins:
            if bin.lower() in venue.lower():
                bins_dict[bin].append(venue)
                break

    return bins_dict


def get_grouped_venue_papers(clients, grouped_venue, only_accepted):
    """
    Get papers from both API v1 and API v2 clients and merge the results.

    Args:
        clients: Tuple of (client_v1, client_v2)
        grouped_venue: List of venue IDs
        only_accepted: Boolean to filter only accepted papers

    Returns:
        Dictionary of papers by venue
    """
    client_v1, client_v2 = clients
    papers = {}

    for venue in grouped_venue:
        papers[venue] = []

        # Get papers from API v1
        submissions_v1 = []
        try:
            if only_accepted:
                submissions_v1 = client_v1.get_all_notes(content={'venueid': venue}, details='directReplies')
            
            else:
                
                single_blind_submissions = client_v1.get_all_notes(invitation=f'{venue}/-/Submission', details='directReplies')
                double_blind_submissions = client_v1.get_all_notes(invitation=f'{venue}/-/Blind_Submission', details='directReplies')
                
                submissions_v1 = single_blind_submissions + double_blind_submissions

        except Exception as e:
            print(f"Error getting papers from API v1 for venue {venue}: {e}")

        # Get papers from API v2
        submissions_v2 = []
        try:
            if only_accepted:
                submissions_v2 = client_v2.get_all_notes(content={'venueid': venue}, details='directReplies')
            
            else:
                
                single_blind_submissions = client_v2.get_all_notes(invitation=f'{venue}/-/Submission', details='directReplies')
                double_blind_submissions = client_v2.get_all_notes(invitation=f'{venue}/-/Blind_Submission', details='directReplies')
                
                submissions_v2 = single_blind_submissions + double_blind_submissions

        except Exception as e:
            print(f"Error getting papers from API v2 for venue {venue}: {e}")

        # Merge submissions from both APIs
        # Use forum IDs to avoid duplicates
        merged_submissions = {}
        for submission in submissions_v1 + submissions_v2:
            if not hasattr(submission, 'forum'):
                continue

            forum = submission.forum
            submission_reviews = get_official_reviews(submission)
            if forum not in merged_submissions:
                submission.content['reviews'] = submission_reviews
                merged_submissions[forum] = submission
                continue

            existing_reviews = merged_submissions[forum].content.get('reviews', [])
            for review in submission_reviews:
                if review not in existing_reviews:
                    existing_reviews.append(review)

        merged_submissions = list(merged_submissions.values())
        papers[venue] += merged_submissions

        print(venue)
        print(f'Number of papers: {len(merged_submissions)}')

    return papers


def get_official_reviews(submission):
    """Return the official review replies exposed with a submission note."""
    details = getattr(submission, 'details', None) or {}
    replies = details.get('directReplies') or details.get('replies') or []
    reviews = []

    for reply in replies:
        if isinstance(reply, dict):
            invitations = reply.get('invitations') or [reply.get('invitation', '')]
            content = reply.get('content') or {}
            signatures = reply.get('signatures') or []
        else:
            invitations = getattr(reply, 'invitations', None) or [getattr(reply, 'invitation', '')]
            content = getattr(reply, 'content', None) or {}
            signatures = getattr(reply, 'signatures', None) or []

        if not any(invitation.endswith('Official_Review') for invitation in invitations):
            continue

        review_content = {
            field: value.get('value', value) if isinstance(value, dict) else value
            for field, value in content.items()
        }
        reviews.append({
            'content': review_content,
            'signatures': signatures,
        })

    return reviews


def get_papers(clients, grouped_venues, only_accepted):
    """
    Get papers for all grouped venues.

    Args:
        clients: Tuple of (client_v1, client_v2)
        grouped_venues: Dictionary of venue IDs by group
        only_accepted: Boolean to filter only accepted papers

    Returns:
        Dictionary of papers by group and venue
    """
    papers = {}
    for group, grouped_venue in grouped_venues.items():
        papers[group] = get_grouped_venue_papers(clients, grouped_venue, only_accepted)

    return papers


class Extractor:
    def __init__(self, fields, subfields, include_subfield=False):
        self.fields = fields
        self.subfields = subfields
        self.include_subfield = include_subfield

    def __call__(self, paper):
        return self.extract(paper)

    def extract(self, paper):
        trimmed_paper = {}
        for field in self.fields:
            trimmed_paper[field] = paper.__getattribute__(field)
        for subfield, fields in self.subfields.items():
            if self.include_subfield:
                trimmed_paper[subfield] = {}
            for field in fields:
                field_value = paper.__getattribute__(subfield)[field]
                if self.include_subfield:
                    trimmed_paper[subfield][field] = field_value
                else:
                    trimmed_paper[field] = field_value

        return trimmed_paper


class Selector:
    def __init__(self, fields=None, options=None, start_idx=0):
        self.idx = start_idx
        self.fields = fields if fields is not None else ['title', 'abstract']
        if options is None:
            self.options = {
                'y':{
                    'desc':'yes',
                    'fn':lambda paper, selected_papers:selected_papers.append(paper)
                },
                'n':{
                    'desc':'no'
                }
            }
        else:
            self.options = options
        self.options['e'] = {'desc':'exit'}

    def __call__(self, papers):
        return self.select(papers)

    def select(self, papers):
        os.system('clear') # i only support unix based systems
        papers_list = papers_to_list(papers)
        selected_papers = []
        while self.idx<len(papers_list):
            paper = papers_list[self.idx]
            self.print_paper(paper)
            decision = self.handle_options(paper, selected_papers)
            if decision=='e': # e will be exit
                print()
                break
            self.idx+=1
        return selected_papers

    def print_paper(self, paper):
        paper_str = ''
        paper_str+='\n' + '-'*os.get_terminal_size().columns + '\n'
        paper_str+=f'Paper {self.idx}\n'
        for field in self.fields:
            paper_str+=f'{field.upper()}: {paper[field]}\n'
        print(f'\r{paper_str}', end='')

    def handle_options(self, paper, selected_papers):
        options_str = ''
        for option, option_dict in self.options.items():
            options_str+=f"{option}: {option_dict['desc']}  "
        decision = input(options_str)
        while decision not in self.options.keys():
            print("Invalid input!")
            decision = input(options_str)
        if self.options[decision].get('fn') is not None:
            self.options[decision]['fn'](paper, selected_papers)
        return decision


class Scraper:
    def __init__(self, conferences, years, keywords, extractor, fpath, selector=None, fns=None, groups=None, only_accepted=True):
        # fns is a list of functions that can be specified by the user each taking in a single paper object as a parameter and returning the modified paper
        self.confs = conferences
        self.years = years
        self.keywords = keywords
        self.extractor = extractor
        self.fpath = fpath
        self.fns = list(fns) if fns is not None else []
        self.groups = list(groups) if groups is not None else ['conference']
        self.only_accepted = only_accepted
        self.selector = selector
        self.filters = []
        # Get both API v1 and API v2 clients
        self.clients = get_client()
        self.papers = None # this'll contain all the papers returned from apply_on_papers

    def __call__(self):
        self.scrape()

    def scrape(self):
        print("Getting venues...")
        venues = get_venues(self.clients, self.confs, self.years)
        print("Getting papers...\n")
        papers = get_papers(self.clients, group_venues(venues, self.groups), self.only_accepted)
        self.papers = papers
        print("\nFiltering papers...")
        papers = self.apply_on_papers(papers)
        if self.selector is not None:
            papers_list = self.selector(papers)
        else:
            papers_list = papers_to_list(papers)
        print("Saving as CSV...")
        to_csv(papers_list, self.fpath)
        print(f"Saved at {self.fpath}")

    def apply_on_papers(self, papers):
        modified_papers = {}
        for group, grouped_venues in papers.items():
            modified_papers[group] = {}
            for venue, venue_papers in grouped_venues.items():
                modified_papers[group][venue] = []
                venue_split = venue.split('/')
                venue_name, venue_year, venue_type = venue_split[0], venue_split[1], venue_split[2]
                for paper in venue_papers:
                    # FILTERS
                    satisfying_keyword, satisfying_filter_type, satisfies = satisfies_any_filters(paper, self.keywords, self.filters)
                    if satisfies:
                        # creating a new field(key) in content attr which is a dict
                        paper.content['match'] = {satisfying_filter_type: satisfying_keyword}
                        paper.content['group'] = group
                        # Execute some custom functions
                        for fn in self.fns:
                            paper = fn(paper)
                        # FIELD EXTRACTION here paper object will be converted into a dict
                        extracted_paper = self.extractor(paper)
                        # add some extra fields
                        extracted_paper['venue'] = venue_name
                        extracted_paper['year'] = venue_year
                        extracted_paper['type'] = venue_type
                        modified_papers[group][venue].append(extracted_paper)
        return modified_papers

    def add_filter(self, filter_, *args, **kwargs):
        self.filters.append((filter_, args, kwargs))
