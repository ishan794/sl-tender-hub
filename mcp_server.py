#!/usr/bin/env python3
"""
Optional Model Context Protocol (MCP) server for AI integration.
Install MCP first with: pip install mcp[cli]
Run this server to connect the tender database to AI tools like Claude Desktop, Cursor, etc.
"""
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("❌ MCP package not installed. Install it with: pip install mcp[cli]")
    exit(1)

from database import init_db, get_tenders, get_db_connection
from typing import Optional

# Initialize MCP server
mcp = FastMCP("Sri Lanka Tender Hub", version="1.0.0")

@mcp.tool()
def search_tenders(
    search_term: Optional[str] = None,
    category: Optional[str] = None,
    status: str = "open",
    closing_after: Optional[str] = None,
    published_after: Optional[str] = None,
    limit: int = 50
) -> list[dict]:
    """
    Search Sri Lankan government and private tenders stored in the local database.
    Use this tool to find open tenders, filter by category, closing date, or search for keywords like "construction", "IT", "Kandy", etc.

    Args:
        search_term: Optional keyword to search in tender title, description, or organization name
        category: Optional category filter: construction, goods, services, consultancy, IT, health, education, transport, agriculture, energy, other
        status: Tender status filter: open (default), closed, awarded, cancelled
        closing_after: Only show tenders closing after this date (use YYYY-MM-DD format)
        published_after: Only show tenders published after this date (use YYYY-MM-DD format)
        limit: Maximum number of results to return (default 50)
    """
    init_db()
    filters = {
        "status": status,
        "category": category,
        "search": search_term,
        "closing_after": closing_after,
        "published_after": published_after
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    return get_tenders(filters=filters, limit=limit)

@mcp.tool()
def get_tender_statistics() -> dict:
    """Get summary statistics about all tenders stored in the local database"""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM tenders")
    total = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as open FROM tenders WHERE status='open'")
    open_count = cursor.fetchone()['open']

    cursor.execute("SELECT COUNT(*) as closing_soon FROM tenders WHERE status='open' AND closing_date <= date('now', '+7 days')")
    closing_soon = cursor.fetchone()['closing_soon']

    cursor.execute("SELECT source_site_id, COUNT(*) as count FROM tenders GROUP BY source_site_id")
    by_source = {row['source_site_id']: row['count'] for row in cursor.fetchall()}

    cursor.execute("SELECT category, COUNT(*) as count FROM tenders GROUP BY category")
    by_category = {row['category']: row['count'] for row in cursor.fetchall()}

    conn.close()

    return {
        "total_tenders_in_database": total,
        "currently_open_tenders": open_count,
        "tenders_closing_in_next_7_days": closing_soon,
        "tenders_by_source_site": by_source,
        "tenders_by_category": by_category
    }

if __name__ == "__main__":
    init_db()
    print("🚀 Starting Sri Lanka Tender Hub MCP server...")
    print("Connect this server to your MCP client (Claude Desktop, Cursor, etc.) to query tender data with AI.")
    mcp.run()
