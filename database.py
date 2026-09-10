import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config import DB_PATH

def get_db_connection():
    """Get a SQLite connection - zero server overhead, file-based storage"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables on first run"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Main tenders table - stores all structured tender data with full details
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tenders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_site_id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        master_group_id TEXT,  -- For cross-site duplicate grouping
        title TEXT NOT NULL,
        organization TEXT,
        published_date DATE,
        closing_date DATETIME,
        location TEXT,
        category TEXT,
        estimated_value TEXT,
        currency TEXT DEFAULT 'LKR',
        description TEXT,
        eligibility TEXT,  -- Bidder eligibility criteria
        bid_bond TEXT,  -- Bid security/bond requirement
        contact_person TEXT,
        contact_email TEXT,
        contact_phone TEXT,
        collection_address TEXT,
        submission_address TEXT,
        document_fee TEXT,  -- Cost of bidding documents
        pre_bid_meeting DATETIME,
        document_links TEXT,  -- JSON array of document download URLs
        source_url TEXT UNIQUE NOT NULL,
        status TEXT DEFAULT 'open',  -- open/closed/awarded/cancelled
        duplicate_of TEXT,  -- If this is a duplicate, points to primary source_id
        is_primary INTEGER DEFAULT 1,  -- 1 = primary record (one per unique tender), 0 = duplicate/alias
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_site_id, source_id)
    )
    ''')

    # Cross-site source links (one tender appearing on multiple sites)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tender_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        master_group_id TEXT NOT NULL,
        source_site_id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_url TEXT NOT NULL,
        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_site_id, source_id)
    )
    ''')

    # Logs for each scraper run to track errors
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scrape_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id TEXT NOT NULL,
        run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL,  -- success/failed/skipped
        tenders_found INTEGER DEFAULT 0,
        new_tenders_added INTEGER DEFAULT 0,
        duplicates_found INTEGER DEFAULT 0,
        error_message TEXT
    )
    ''')

    # Indexes for fast queries (no slow table scans)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tenders_closing_date ON tenders(closing_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tenders_status ON tenders(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tenders_category ON tenders(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tenders_source ON tenders(source_site_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tenders_primary ON tenders(is_primary)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tenders_master ON tenders(master_group_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tender_sources_master ON tender_sources(master_group_id)')

    conn.commit()
    conn.close()

def get_all_existing_tenders(limit: int = 5000) -> List[Dict]:
    """Get all primary (non-duplicate) tenders for duplicate comparison"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tenders WHERE is_primary = 1 ORDER BY published_date DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        row_dict = dict(row)
        row_dict['document_links'] = json.loads(row_dict['document_links']) if row_dict['document_links'] else []
        results.append(row_dict)
    return results

def insert_tender(tender_data: Dict, master_group_id: str = None, is_primary: bool = 1, duplicate_of: str = None) -> bool:
    """Insert a new tender - automatically skips duplicates, returns True if added"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if not master_group_id:
            import hashlib
            master_group_id = hashlib.md5(tender_data['source_url'].encode()).hexdigest()[:12]

        cursor.execute('''
        INSERT INTO tenders (
            source_site_id, source_id, master_group_id, title, organization, published_date,
            closing_date, location, category, estimated_value, currency, description,
            eligibility, bid_bond, contact_person, contact_email, contact_phone,
            collection_address, submission_address, document_fee, pre_bid_meeting,
            document_links, source_url, status, is_primary, duplicate_of
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tender_data['source_site_id'],
            tender_data['source_id'],
            master_group_id,
            tender_data['title'],
            tender_data.get('organization'),
            tender_data.get('published_date'),
            tender_data.get('closing_date'),
            tender_data.get('location'),
            tender_data.get('category', 'other'),
            tender_data.get('estimated_value'),
            tender_data.get('currency', 'LKR'),
            tender_data.get('description'),
            tender_data.get('eligibility'),
            tender_data.get('bid_bond'),
            tender_data.get('contact_person'),
            tender_data.get('contact_email'),
            tender_data.get('contact_phone'),
            tender_data.get('collection_address'),
            tender_data.get('submission_address'),
            tender_data.get('document_fee'),
            tender_data.get('pre_bid_meeting'),
            json.dumps(tender_data.get('document_links', [])),
            tender_data['source_url'],
            tender_data.get('status', 'open'),
            is_primary,
            duplicate_of
        ))

        # Add source mapping
        cursor.execute('''
        INSERT OR IGNORE INTO tender_sources (master_group_id, source_site_id, source_id, source_url)
        VALUES (?, ?, ?, ?)
        ''', (master_group_id, tender_data['source_site_id'], tender_data['source_id'], tender_data['source_url']))

        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Duplicate tender already exists, skip
        return False
    finally:
        conn.close()

def add_duplicate_source(master_group_id: str, source_site_id: str, source_id: str, source_url: str):
    """Register that an existing tender also appears on another site (cross-site duplicate)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR IGNORE INTO tender_sources (master_group_id, source_site_id, source_id, source_url)
    VALUES (?, ?, ?, ?)
    ''', (master_group_id, source_site_id, source_id, source_url))
    conn.commit()
    conn.close()

def log_scrape_run(site_id: str, status: str, tenders_found: int = 0, new_tenders: int = 0,
                   duplicates: int = 0, error_message: Optional[str] = None):
    """Log result of a scraper run"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO scrape_logs (site_id, status, tenders_found, new_tenders_added, duplicates_found, error_message)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (site_id, status, tenders_found, new_tenders, duplicates, error_message))
    conn.commit()
    conn.close()

def get_tenders(filters: Optional[Dict] = None, limit: int = 100, page: int = 1, include_duplicates: bool = False) -> Dict:
    """Query tenders with optional filters (search, category, status, date) - API ready, paginated"""
    conn = get_db_connection()
    cursor = conn.cursor()
    base_query = "FROM tenders WHERE 1=1"
    count_query = "SELECT COUNT(*) as total FROM tenders WHERE 1=1"
    if not include_duplicates:
        base_query += " AND is_primary = 1"
        count_query += " AND is_primary = 1"
    params = []

    if filters:
        if filters.get('status'):
            base_query += " AND status = ?"
            count_query += " AND status = ?"
            params.append(filters['status'])
        if filters.get('category'):
            base_query += " AND category = ?"
            count_query += " AND category = ?"
            params.append(filters['category'])
        if filters.get('source_site_id'):
            base_query += " AND source_site_id = ?"
            count_query += " AND source_site_id = ?"
            params.append(filters['source_site_id'])
        if filters.get('closing_after'):
            base_query += " AND (closing_date >= ? OR closing_date IS NULL)"
            count_query += " AND (closing_date >= ? OR closing_date IS NULL)"
            params.append(filters['closing_after'])
        if filters.get('closing_before'):
            base_query += " AND closing_date <= ?"
            count_query += " AND closing_date <= ?"
            params.append(filters['closing_before'])
        if filters.get('published_after'):
            base_query += " AND (published_date >= ? OR published_date IS NULL)"
            count_query += " AND (published_date >= ? OR published_date IS NULL)"
            params.append(filters['published_after'])
        if filters.get('organization'):
            base_query += " AND organization LIKE ?"
            count_query += " AND organization LIKE ?"
            params.append(f"%{filters['organization']}%")
        if filters.get('search'):
            base_query += " AND (title LIKE ? OR description LIKE ? OR organization LIKE ?)"
            count_query += " AND (title LIKE ? OR description LIKE ? OR organization LIKE ?)"
            search_term = f"%{filters['search']}%"
            params.extend([search_term, search_term, search_term])

    # Get total count for pagination
    cursor.execute(count_query, params)
    total = cursor.fetchone()['total']
    total_pages = (total + limit - 1) // limit
    offset = (page - 1) * limit

    # Get results
    query = f"SELECT * {base_query} ORDER BY COALESCE(published_date, scraped_at) DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Get all sources for each tender
    results = []
    for row in rows:
        row_dict = dict(row)
        row_dict['document_links'] = json.loads(row_dict['document_links']) if row_dict['document_links'] else []

        # Get all sites where this tender appears
        cursor.execute('SELECT source_site_id, source_url FROM tender_sources WHERE master_group_id = ?',
                      (row_dict['master_group_id'],))
        row_dict['available_on_sites'] = [dict(r) for r in cursor.fetchall()]
        results.append(row_dict)

    conn.close()

    return {
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "limit": limit,
        "results": results
    }

def get_tender_sources(master_group_id: str) -> List[Dict]:
    """Get all sources/websites where a particular tender appears"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tender_sources WHERE master_group_id = ?', (master_group_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_statistics() -> Dict:
    """Get summary statistics for API dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM tenders WHERE is_primary = 1")
    total_unique = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as open FROM tenders WHERE status='open' AND is_primary = 1")
    open_count = cursor.fetchone()['open']

    cursor.execute("SELECT COUNT(*) as closing_soon FROM tenders WHERE status='open' AND closing_date <= date('now', '+7 days') AND closing_date >= date('now') AND is_primary = 1")
    closing_soon = cursor.fetchone()['closing_soon']

    cursor.execute("SELECT COUNT(DISTINCT source_site_id) as sites FROM tenders")
    sites_count = cursor.fetchone()['sites']

    cursor.execute("SELECT category, COUNT(*) as count FROM tenders WHERE is_primary = 1 GROUP BY category")
    by_category = {row['category']: row['count'] for row in cursor.fetchall()}

    cursor.execute("SELECT source_site_id, COUNT(*) as count FROM tenders WHERE is_primary = 1 GROUP BY source_site_id ORDER BY count DESC")
    by_source = {row['source_site_id']: row['count'] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) as dupes FROM tender_sources")
    total_sources = cursor.fetchone()['dupes']

    conn.close()

    return {
        "total_unique_tenders": total_unique,
        "total_source_listings": total_sources,
        "currently_open_tenders": open_count,
        "tenders_closing_in_next_7_days": closing_soon,
        "sources_scraped": sites_count,
        "by_category": by_category,
        "by_source_site": by_source,
        "last_updated": datetime.now().isoformat()
    }

def mark_expired_tenders():
    """Automatically mark tenders as closed if closing date has passed (run daily)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tenders SET status = 'closed'
        WHERE status = 'open' AND closing_date IS NOT NULL AND closing_date < date('now')
    """)
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    return updated

def delete_expired_tenders(days_after_closing: int = 20):
    """
    Automatically DELETE tenders that have been closed for more than `days_after_closing` days (default 20 days).
    This keeps database size small and only shows relevant/recent tenders.
    Also deletes related source mappings for deleted tenders.
    Returns number of tenders deleted.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Find expired master group IDs to delete
    cursor.execute("""
        SELECT DISTINCT master_group_id FROM tenders
        WHERE status = 'closed'
        AND closing_date IS NOT NULL
        AND closing_date < date('now', ?)
    """, (f'-{days_after_closing} days',))
    expired_groups = [row['master_group_id'] for row in cursor.fetchall()]

    if not expired_groups:
        conn.close()
        return 0

    placeholders = ','.join(['?' for _ in expired_groups])
    # Delete source mappings first
    cursor.execute(f"DELETE FROM tender_sources WHERE master_group_id IN ({placeholders})", expired_groups)
    # Delete all tender records (primary + duplicates)
    cursor.execute(f"DELETE FROM tenders WHERE master_group_id IN ({placeholders})", expired_groups)
    deleted = cursor.rowcount

    conn.commit()
    conn.close()
    return deleted
