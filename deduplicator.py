"""
Smart Cross-Site Duplicate Detection for Tenders
Uses fuzzy matching of titles + contract numbers + organization to identify duplicates across different websites
RAM usage: <10MB, no ML/AI models required
"""
import re
from collections import defaultdict
from urllib.parse import urlparse
from typing import Dict, Optional, List

# Common words to ignore when comparing titles
STOP_WORDS = {
    'sri', 'lanka', 'ltd', 'limited', 'company', 'corporation', 'authority', 'board',
    'ministry', 'department', 'government', 'procurement', 'notice', 'invitation', 'bids',
    'bid', 'tender', 'tenders', 'for', 'the', 'of', 'and', 'to', 'in', 'on', 'at', 'by',
    'no', 'nos', 'number', 'ref', 'reference', 'public', 'private', 'national',
    'supply', 'providing', 'provision', 'construction', 'work', 'works', 'services',
    'inviting', 'sealed', 'quotations', 'proposals', 'rfp', 'ifb', 'icb', 'ncb',
    'english', 'sinhala', 'tamil', 'advertisement', 'ad', 'click', 'here', 'download',
    'dated', 'date', 'closing', 'submission', 'open', 'closed', 'new', 'brand'
}

def normalize_text(text: str) -> str:
    """Normalize tender title for comparison: lowercase, remove punctuation, remove stop words"""
    if not text:
        return ""
    # Remove HTML tags if any
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove special characters and numbers that vary by site
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Extract alphanumeric tokens
    tokens = []
    for word in text.split():
        if word not in STOP_WORDS and len(word) > 2:
            # Keep contract numbers/identifiers (they are unique per tender)
            if len(word) >= 5 or any(c.isdigit() for c in word):
                tokens.append(word)
    return ' '.join(sorted(tokens))

def extract_contract_number(text: str) -> Optional[str]:
    """Extract unique contract/reference/bid number from title"""
    patterns = [
        r'CONTRACT\s*NO:?\s*([A-Z0-9\-/._]{5,})',
        r'BID\s*NO:?\s*([A-Z0-9\-/._]{5,})',
        r'REF(?:ERENCE)?:?\s*([A-Z0-9\-/._]{5,})',
        r'RFP\s*:?\s*([A-Z0-9\-/._]{5,})',
        r'IFB\s*:?\s*([A-Z0-9\-/._]{5,})',
        r'ITB\s*NO:?\s*([A-Z0-9\-/._]{5,})',
        r'TENDER\s*NO:?\s*([A-Z0-9\-/._]{5,})',
        r'([A-Z]{2,}[-/][A-Z0-9\-/._]{6,})',
    ]
    if not text:
        return None
    text_upper = text.upper()
    for pattern in patterns:
        match = re.search(pattern, text_upper)
        if match:
            return match.group(1).strip().strip('.-/')
    return None

def get_content_hash(title: str, organization: str = None) -> str:
    """Generate a similarity hash for fuzzy matching"""
    import hashlib
    norm_title = normalize_text(title)
    if organization:
        norm_title += "|" + normalize_text(organization)
    return hashlib.md5(norm_title.encode()).hexdigest()[:12]

def calculate_similarity(title1: str, title2: str) -> float:
    """Calculate text similarity between two titles (0-1 score, lightweight Jaccard)"""
    set1 = set(normalize_text(title1).split())
    set2 = set(normalize_text(title2).split())
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0

def find_matching_tender(new_tender: Dict, existing_tenders: List[Dict]) -> Optional[str]:
    """
    Check if new tender is a duplicate of any existing tender.
    Returns existing tender source_id if duplicate found, None otherwise.
    Matching priority:
    1. Same contract number = 100% duplicate
    2. Same content hash = duplicate
    3. Title similarity > 0.85 = duplicate

    NOTE: O(n) per call. For very large datasets use build_index() +
    find_matching_tender_fast() instead.
    """
    new_contract = extract_contract_number(new_tender.get('title', ''))
    new_norm = normalize_text(new_tender.get('title', ''))
    new_org_norm = normalize_text(new_tender.get('organization', ''))
    new_hash = get_content_hash(new_tender.get('title', ''), new_tender.get('organization', ''))

    best_match = None
    best_score = 0.0

    for existing in existing_tenders:
        # 1. Contract number exact match (fastest check)
        existing_contract = extract_contract_number(existing.get('title', ''))
        if new_contract and existing_contract:
            if new_contract == existing_contract:
                # Same contract number = definite duplicate
                return existing['source_id']

        # 2. Skip different organizations entirely (different government bodies won't have same tender)
        existing_org_norm = normalize_text(existing.get('organization', ''))
        if new_org_norm and existing_org_norm:
            org_similarity = len(set(new_org_norm.split()) & set(existing_org_norm.split())) / max(len(set(new_org_norm.split()) | set(existing_org_norm.split())), 1)
            if org_similarity < 0.2:
                continue  # Different organization, not duplicate

        # 3. Content hash match
        existing_hash = get_content_hash(existing.get('title', ''), existing.get('organization', ''))
        if new_hash == existing_hash:
            return existing['source_id']

        # 4. Fuzzy title similarity
        similarity = calculate_similarity(new_tender.get('title', ''), existing.get('title', ''))
        if similarity > 0.85 and similarity > best_score:
            best_score = similarity
            best_match = existing['source_id']

    return best_match


def build_index(existing_tenders: List[Dict]) -> Dict:
    """Precompute lookup structures so duplicate detection scales to 100k+ tenders.

    Replaces the O(n) scan of find_matching_tender with:
      - O(1) exact lookups (contract number, content hash)
      - a token index that only fuzzy-compares against tenders sharing a
        rare title token (instead of every tender).
    """
    by_contract = {}
    by_hash = {}
    token_index = defaultdict(set)
    records = {}

    for e in existing_tenders:
        sid = e.get('source_id')
        if not sid:
            continue
        title = e.get('title', '') or ''
        org = e.get('organization', '') or ''
        contract = extract_contract_number(title)
        title_tokens = set(normalize_text(title).split())
        org_tokens = set(normalize_text(org).split())
        chash = get_content_hash(title, org)

        records[sid] = {
            'contract': contract,
            'hash': chash,
            'title_tokens': title_tokens,
            'org_tokens': org_tokens,
        }
        if contract:
            by_contract[contract] = sid
        by_hash[chash] = sid
        for tok in title_tokens:
            token_index[tok].add(sid)

    return {
        'by_contract': by_contract,
        'by_hash': by_hash,
        'token_index': token_index,
        'records': records,
    }


def index_add(index: Dict, tender: Dict) -> None:
    """Register a newly-inserted tender in an existing index."""
    sid = tender.get('source_id')
    if not sid:
        return
    title = tender.get('title', '') or ''
    org = tender.get('organization', '') or ''
    contract = extract_contract_number(title)
    title_tokens = set(normalize_text(title).split())
    org_tokens = set(normalize_text(org).split())
    chash = get_content_hash(title, org)

    index['records'][sid] = {
        'contract': contract,
        'hash': chash,
        'title_tokens': title_tokens,
        'org_tokens': org_tokens,
    }
    if contract:
        index['by_contract'][contract] = sid
    index['by_hash'][chash] = sid
    for tok in title_tokens:
        index['token_index'][tok].add(sid)


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def find_matching_tender_fast(new_tender: Dict, index: Dict) -> Optional[str]:
    """Indexed equivalent of find_matching_tender (same rules, near O(1) per call)."""
    title = new_tender.get('title', '') or ''
    org = new_tender.get('organization', '') or ''

    new_contract = extract_contract_number(title)
    new_hash = get_content_hash(title, org)
    new_title_tokens = set(normalize_text(title).split())
    new_org_tokens = set(normalize_text(org).split())

    # 1. Contract number exact match
    if new_contract and new_contract in index['by_contract']:
        return index['by_contract'][new_contract]

    # 2. Content hash match
    if new_hash in index['by_hash']:
        return index['by_hash'][new_hash]

    # 3. Fuzzy title similarity - only compare against tenders sharing a rare
    #    title token. A true >0.85 match shares most tokens, including rare ones.
    rare_tokens = sorted(new_title_tokens, key=lambda t: len(index['token_index'].get(t, ())))[:5]
    candidates = set()
    for tok in rare_tokens:
        candidates |= index['token_index'].get(tok, set())

    best_match = None
    best_score = 0.0
    for sid in candidates:
        rec = index['records'][sid]
        # Skip different organizations entirely
        if new_org_tokens and rec['org_tokens']:
            if _jaccard(new_org_tokens, rec['org_tokens']) < 0.2:
                continue
        similarity = _jaccard(new_title_tokens, rec['title_tokens'])
        if similarity > 0.85 and similarity > best_score:
            best_score = similarity
            best_match = sid

    return best_match
