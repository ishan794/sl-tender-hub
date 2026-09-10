"""
Sri Lanka Tender Sources Registry - All 85 verified sources
Priority levels: 1 = highest (frequent updates, most tenders), 2 = medium, 3 = low
"""
from dataclasses import dataclass
from typing import Optional

from credentials import MY_SITE  # link + login e-mail + password (see credentials.py)

@dataclass
class TenderSource:
    id: str
    name: str
    base_url: str
    tender_url: Optional[str]
    type: str  # government/soe/ministry/municipal/university/private_aggregator/statutory
    priority: int  # 1=critical, 2=important, 3=low
    scraper_strategy: str = "generic_wp"  # generic_wp / nextjs / joomla / custom / html_list

ALL_SOURCES = [
    # ===== PRIORITY 1: Central Government / Major Portals =====
    TenderSource("promise", "PROMISe e-GP Sri Lanka", "https://www.promise.lk", "https://www.promise.lk/egp2/", "government", 1, "promise"),
    TenderSource("npc", "National Procurement Commission", "https://nprocom.gov.lk", "https://nprocom.gov.lk/procurement-notices/", "government", 1, "npc"),
    TenderSource("npc_epms", "NPC e-Procurement Monitoring System", "https://epms.nprocom.gov.lk", "https://epms.nprocom.gov.lk/", "government", 1, "custom"),
    TenderSource("treasury", "Ministry of Finance / Treasury", "https://www.treasury.gov.lk", "https://www.treasury.gov.lk/procurement/procurement-notices?page=1", "government", 1, "nextjs"),
    TenderSource("ceb", "Ceylon Electricity Board", "https://ceb.lk", "https://ceb.lk/tenders", "soe", 1, "generic_wp"),
    TenderSource("nwsdb", "National Water Supply & Drainage Board", "https://www.waterboard.lk", "https://www.waterboard.lk/tenders/", "soe", 1, "generic_wp"),
    TenderSource("railway", "Sri Lanka Railways", "https://www.railway.gov.lk", "https://www.railway.gov.lk/web/index.php?Itemid=197&id=51&lang=en&layout=blog&option=com_content&view=category", "soe", 1, "joomla"),
    TenderSource("slpa", "Sri Lanka Ports Authority", "https://www.slpa.lk", "https://www.slpa.lk/tenders", "soe", 1, "generic_wp"),
    TenderSource("srilankan", "SriLankan Airlines", "https://www.srilankan.com", "https://www.srilankan.com/en_uk/corporate/tender-notices", "soe", 1, "custom"),
    TenderSource("mahaweli", "Mahaweli Authority", "https://mahaweli.gov.lk", "https://mahaweli.gov.lk/tenders.html", "statutory", 1, "mahaweli"),
    TenderSource("irrigation", "Department of Irrigation", "https://www.irrigation.gov.lk", "https://www.irrigation.gov.lk/web/index.php?id=143&lang=en&option=com_content&view=article", "government", 1, "joomla"),
    TenderSource("spmc", "State Pharmaceuticals Manufacturing Corporation", "https://spmc.gov.lk", "https://spmc.gov.lk/media/tenders", "soe", 1, "generic_wp"),
    TenderSource("hadabima", "Hadabima Authority", "https://hadabima.gov.lk", "https://hadabima.gov.lk/en/procurement-notices/", "statutory", 1, "generic_wp"),
    TenderSource("nso", "National System Operator", "https://nso.lk", "https://nso.lk/procurement/tender-notices", "soe", 1, "generic_wp"),
    TenderSource("rda", "Road Development Authority", "https://www.rda.gov.lk", "https://www.rda.gov.lk/tenders", "government", 1, "generic_wp"),
    TenderSource("customs", "Sri Lanka Customs", "https://www.customs.gov.lk", "https://www.customs.gov.lk/tenders", "government", 1, "generic_wp"),
    TenderSource("cbsl", "Central Bank of Sri Lanka", "https://www.cbsl.gov.lk", "https://www.cbsl.gov.lk/en/tenders", "government", 1, "custom"),
    TenderSource("leco", "Lanka Electricity Company", "https://www.leco.lk", "https://www.leco.lk/tenders", "soe", 1, "generic_wp"),
    TenderSource("cpc", "Ceylon Petroleum Corporation", "https://ceypetco.gov.lk", "https://ceypetco.gov.lk/tenders", "soe", 1, "generic_wp"),
    TenderSource("cpstl", "Ceylon Petroleum Storage Terminals", "https://www.cpstl.lk", "https://www.cpstl.lk/tenders", "soe", 1, "generic_wp"),
    TenderSource("spc", "State Pharmaceuticals Corporation", "https://www.spc.lk", "https://www.spc.lk/tenders", "soe", 1, "generic_wp"),
    TenderSource("uda", "Urban Development Authority", "https://www.uda.gov.lk", "https://www.uda.gov.lk/tenders", "government", 1, "generic_wp"),
    TenderSource("slpost", "Sri Lanka Post", "https://slpost.gov.lk", "https://slpost.gov.lk/notice/procurement/", "government", 1, "slpost"),

    # ===== PRIORITY 2: Ministries & Statutory Bodies =====
    TenderSource("moj", "Ministry of Justice", "https://www.moj.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("mfa", "Ministry of Foreign Affairs", "https://www.mfa.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("pubad", "Ministry of Public Administration", "https://pubad.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("defence", "Ministry of Defence", "https://www.defence.lk", None, "ministry", 2, "discover"),
    TenderSource("health", "Ministry of Health", "https://www.health.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("moe", "Ministry of Education", "https://moe.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("agrimin", "Ministry of Agriculture", "https://www.agrimin.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("transport", "Ministry of Transport", "https://www.transport.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("industry", "Ministry of Industries", "https://www.industry.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("env", "Ministry of Environment", "https://env.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("energy", "Ministry of Energy", "https://energy.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("fisheries", "Ministry of Fisheries", "https://www.fisheries.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("tourism", "Ministry of Tourism", "https://tourism.gov.lk", None, "ministry", 2, "discover"),
    TenderSource("pucsl", "Public Utilities Commission", "https://www.pucsl.gov.lk", "https://www.pucsl.gov.lk/contact-us/tender-notices/", "statutory", 2, "generic_wp"),
    TenderSource("kandymc", "Kandy Municipal Council", "https://kandy.mc.gov.lk", "https://kandy.mc.gov.lk/Tenders", "municipal", 2, "generic_wp"),
    TenderSource("boc", "Bank of Ceylon", "https://www.boc.lk", None, "soe", 2, "discover"),
    TenderSource("peoplesbank", "People's Bank", "https://www.peoplesbank.lk", None, "soe", 2, "discover"),
    TenderSource("nsb", "National Savings Bank", "https://www.nsb.lk", None, "soe", 2, "discover"),
    TenderSource("slt", "Sri Lanka Telecom", "https://www.slt.lk", None, "soe", 2, "discover"),
    TenderSource("dialog", "Dialog Axiata", "https://www.dialog.lk", None, "private", 2, "discover"),
    TenderSource("litro", "Litro Gas Lanka", "https://www.litrogas.com", None, "soe", 2, "discover"),
    TenderSource("lankahospitals", "Lanka Hospitals", "https://www.lankahospitals.com", None, "private", 2, "discover"),
    TenderSource("slcert", "Sri Lanka CERT", "https://www.cert.gov.lk", None, "statutory", 2, "discover"),
    TenderSource("lankasugar", "Lanka Sugar Company", "https://www.lankasugar.lk", None, "soe", 2, "discover"),
    TenderSource("lankamineralsands", "Lanka Mineral Sands", "https://lankamineralsands.com", None, "soe", 2, "discover"),
    TenderSource("paranthan", "Paranthan Chemicals Company", "https://www.paranthanchemicals.lk", None, "soe", 2, "discover"),
    TenderSource("nfs", "National Fertilizer Secretariat", "https://www.nfs.gov.lk", None, "statutory", 2, "discover"),
    TenderSource("teaboard", "Sri Lanka Tea Board", "https://www.srilankateaboard.lk", None, "statutory", 2, "discover"),
    TenderSource("neda", "National Enterprise Development Authority", "https://neda.gov.lk", None, "statutory", 2, "discover"),
    TenderSource("idb", "Industrial Development Board", "https://www.idb.gov.lk", None, "statutory", 2, "discover"),
    TenderSource("cda", "Coconut Development Authority", "https://www.cda.gov.lk", None, "statutory", 2, "discover"),
    TenderSource("rubberdev", "Rubber Development Department", "https://www.rubberdev.gov.lk", None, "government", 2, "discover"),
    TenderSource("cfc", "Ceylon Fisheries Corporation", "https://www.cfc.gov.lk", None, "soe", 2, "discover"),
    TenderSource("nldb", "National Livestock Development Board", "https://nldb.gov.lk", None, "soe", 2, "discover"),
    TenderSource("sltda", "Sri Lanka Tourism Development Authority", "https://www.sltda.gov.lk", None, "statutory", 2, "discover"),
    TenderSource("ntc", "National Transport Commission", "https://www.ntc.gov.lk", None, "statutory", 2, "discover"),
    TenderSource("caasl", "Civil Aviation Authority", "https://www.caa.lk", None, "statutory", 2, "discover"),
    TenderSource("aasl", "Airport & Aviation Services", "https://www.airport.lk", None, "soe", 2, "discover"),
    TenderSource("slsi", "Sri Lanka Standards Institution", "https://www.slsi.lk", None, "statutory", 2, "discover"),
    TenderSource("srilankainsurance", "Sri Lanka Insurance", "https://www.srilankainsurance.com", None, "private", 2, "discover"),
    TenderSource("nitf", "National Insurance Trust Fund", "https://www.nitf.lk", None, "statutory", 2, "discover"),

    # ===== PRIORITY 3: Universities =====
    TenderSource("ugc", "University Grants Commission", "https://www.ugc.ac.lk", None, "university", 3, "discover"),
    TenderSource("sliit", "Sri Lanka Institute of Information Technology", "https://www.sliit.lk", "https://www.sliit.lk/tender-notices/", "university", 3, "generic_wp"),
    TenderSource("uovt", "University of Vocational Technology", "https://www.uovt.ac.lk", "https://www.uovt.ac.lk/en/staff/supply", "university", 3, "generic_wp"),
    TenderSource("colombo", "University of Colombo", "https://cmb.ac.lk", None, "university", 3, "discover"),
    TenderSource("peradeniya", "University of Peradeniya", "https://www.pdn.ac.lk", None, "university", 3, "discover"),
    TenderSource("sjp", "University of Sri Jayewardenepura", "https://www.sjp.ac.lk", None, "university", 3, "discover"),
    TenderSource("kelaniya", "University of Kelaniya", "https://www.kln.ac.lk", None, "university", 3, "discover"),
    TenderSource("moratuwa", "University of Moratuwa", "https://uom.lk", None, "university", 3, "discover"),
    TenderSource("ruhuna", "University of Ruhuna", "https://www.ruh.ac.lk", None, "university", 3, "discover"),
    TenderSource("ousl", "Open University of Sri Lanka", "https://ou.ac.lk", None, "university", 3, "discover"),
    TenderSource("wayamba", "Wayamba University", "https://wyb.ac.lk", None, "university", 3, "discover"),
    TenderSource("rajarata", "Rajarata University", "https://www.rjt.ac.lk", None, "university", 3, "discover"),
    TenderSource("sabaragamuwa", "Sabaragamuwa University", "https://www.sab.ac.lk", None, "university", 3, "discover"),
    TenderSource("eastern", "Eastern University", "https://www.esn.ac.lk", None, "university", 3, "discover"),
    TenderSource("seusl", "South Eastern University", "https://www.seu.ac.lk", None, "university", 3, "discover"),

    # ===== Private Aggregators =====
    TenderSource("tenders_lk", "Tenders.lk", "https://www.tenders.lk", "https://backend.tenders.lk/api/tenders?page=1", "private_aggregator", 1, "tenders_lk"),
    TenderSource("srilankatender", "SriLankaTender.com", "https://www.srilankatender.com", "https://www.srilankatender.com/tenders.php", "private_aggregator", 1, "srilankatender"),
    TenderSource("smarttenders", "SmartTenders.lk", "https://smarttenders.lk", "https://admin.smarttenders.lk/api/tenders", "private_aggregator", 1, "smarttenders"),
    TenderSource("etenders", "eTenders.lk", "https://etenders.lk", "https://api.etenders.lk", "private_aggregator", 1, "etenders"),
    TenderSource("tendernotices", "TenderNotices.lk", "https://www.tendernotices.lk", "https://www.tendernotices.lk/tenders-sri-lanka", "private_aggregator", 1, "tendernotices"),
    TenderSource("un_srilanka", "UN Sri Lanka Government Tenders", "https://www.un.int/srilanka", "https://www.un.int/srilanka/srilanka/government-tenders", "aggregator", 3, "generic_wp"),

    # ===== Login-protected (private) portals =====
    # The link + login e-mail + password are NOT stored here - they live in
    # credentials.py (or the .env file). Fill the pointers there and this
    # source starts working automatically.
    TenderSource(
        "my_tender_site",
        MY_SITE.site_name or "My Tender Site (login required)",
        MY_SITE.site_url or "https://configure-in-credentials.py",
        MY_SITE.list_url or None,
        "private_portal", 1, "authenticated",
    ),
]

def get_sources_by_priority(priority: int = None):
    if priority:
        return [s for s in ALL_SOURCES if s.priority == priority]
    return ALL_SOURCES

def get_source(source_id: str):
    for s in ALL_SOURCES:
        if s.id == source_id:
            return s
    return None
