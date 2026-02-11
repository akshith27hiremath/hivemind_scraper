"""
Comprehensive alias map for S&P 500 companies.

Maps common names, abbreviations, brand names, subsidiaries, and colloquial
references to their official ticker symbols. Used for entity extraction from
financial news headlines and summaries.

Keys: lowercase alias strings
Values: ticker strings (uppercase)

Generated from the 503 S&P 500 constituents (as of Feb 2026).
"""

COMPANY_ALIASES = {

    # =========================================================================
    # MEGA-CAP TECHNOLOGY
    # =========================================================================

    # AAPL - Apple Inc.
    "apple": "AAPL",
    "apple inc.": "AAPL",
    "apple inc": "AAPL",
    "iphone": "AAPL",
    "ipad": "AAPL",
    "macbook": "AAPL",
    "apple watch": "AAPL",
    "apple vision pro": "AAPL",
    "airpods": "AAPL",
    "app store": "AAPL",
    "apple tv+": "AAPL",
    "apple tv plus": "AAPL",
    "apple music": "AAPL",
    "apple intelligence": "AAPL",
    "tim cook": "AAPL",

    # MSFT - Microsoft
    "microsoft": "MSFT",
    "microsoft corp": "MSFT",
    "microsoft corporation": "MSFT",
    "msft": "MSFT",
    "windows": "MSFT",
    "azure": "MSFT",
    "microsoft azure": "MSFT",
    "xbox": "MSFT",
    "office 365": "MSFT",
    "microsoft 365": "MSFT",
    "microsoft teams": "MSFT",
    "teams": "MSFT",
    "linkedin": "MSFT",
    "github": "MSFT",
    "bing": "MSFT",
    "copilot": "MSFT",
    "microsoft copilot": "MSFT",
    "satya nadella": "MSFT",
    "activision blizzard": "MSFT",

    # GOOGL / GOOG - Alphabet Inc.
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "alphabet inc": "GOOGL",
    "alphabet inc.": "GOOGL",
    "alphabet class a": "GOOGL",
    "alphabet class c": "GOOG",
    "googl": "GOOGL",
    "goog": "GOOG",
    "youtube": "GOOGL",
    "google cloud": "GOOGL",
    "gmail": "GOOGL",
    "chrome": "GOOGL",
    "android": "GOOGL",
    "google maps": "GOOGL",
    "waymo": "GOOGL",
    "deepmind": "GOOGL",
    "google deepmind": "GOOGL",
    "google ads": "GOOGL",
    "google pixel": "GOOGL",
    "pixel phone": "GOOGL",
    "sundar pichai": "GOOGL",
    "gemini ai": "GOOGL",

    # AMZN - Amazon
    "amazon": "AMZN",
    "amazon.com": "AMZN",
    "amazon inc": "AMZN",
    "amazon.com inc": "AMZN",
    "amzn": "AMZN",
    "aws": "AMZN",
    "amazon web services": "AMZN",
    "prime video": "AMZN",
    "amazon prime": "AMZN",
    "kindle": "AMZN",
    "alexa": "AMZN",
    "amazon alexa": "AMZN",
    "whole foods": "AMZN",
    "twitch": "AMZN",
    "ring doorbell": "AMZN",
    "amazon go": "AMZN",
    "andy jassy": "AMZN",
    "jeff bezos": "AMZN",

    # META - Meta Platforms
    "meta": "META",
    "meta platforms": "META",
    "meta platforms inc": "META",
    "meta platforms inc.": "META",
    "facebook": "META",
    "instagram": "META",
    "whatsapp": "META",
    "messenger": "META",
    "facebook messenger": "META",
    "oculus": "META",
    "meta quest": "META",
    "threads app": "META",
    "mark zuckerberg": "META",
    "zuckerberg": "META",

    # NVDA - Nvidia
    "nvidia": "NVDA",
    "nvidia corp": "NVDA",
    "nvidia corporation": "NVDA",
    "nvda": "NVDA",
    "geforce": "NVDA",
    "nvidia gpu": "NVDA",
    "cuda": "NVDA",
    "nvidia ai": "NVDA",
    "jensen huang": "NVDA",
    "nvidia dgx": "NVDA",
    "nvidia h100": "NVDA",
    "nvidia a100": "NVDA",
    "nvidia blackwell": "NVDA",

    # TSLA - Tesla, Inc.
    "tesla": "TSLA",
    "tesla inc": "TSLA",
    "tesla inc.": "TSLA",
    "tesla motors": "TSLA",
    "tsla": "TSLA",
    "model 3": "TSLA",
    "model y": "TSLA",
    "model s": "TSLA",
    "model x": "TSLA",
    "cybertruck": "TSLA",
    "supercharger": "TSLA",
    "tesla supercharger": "TSLA",
    "tesla energy": "TSLA",
    "tesla autopilot": "TSLA",
    "tesla fsd": "TSLA",
    "elon musk": "TSLA",

    # AVGO - Broadcom
    "broadcom": "AVGO",
    "broadcom inc": "AVGO",
    "broadcom inc.": "AVGO",
    "avgo": "AVGO",
    "broadcom vmware": "AVGO",
    "vmware": "AVGO",

    # ORCL - Oracle Corporation
    "oracle": "ORCL",
    "oracle corp": "ORCL",
    "oracle corporation": "ORCL",
    "oracle cloud": "ORCL",
    "larry ellison": "ORCL",
    "oracle database": "ORCL",

    # CRM - Salesforce
    "salesforce": "CRM",
    "salesforce inc": "CRM",
    "salesforce.com": "CRM",
    "salesforce inc.": "CRM",
    "marc benioff": "CRM",
    "slack": "CRM",
    "tableau": "CRM",

    # AMD - Advanced Micro Devices
    "amd": "AMD",
    "advanced micro devices": "AMD",
    "advanced micro devices inc": "AMD",
    "radeon": "AMD",
    "ryzen": "AMD",
    "epyc": "AMD",
    "lisa su": "AMD",
    "xilinx": "AMD",

    # INTC - Intel
    "intel": "INTC",
    "intel corp": "INTC",
    "intel corporation": "INTC",
    "intc": "INTC",
    "intel foundry": "INTC",
    "intel core": "INTC",
    "pat gelsinger": "INTC",

    # CSCO - Cisco
    "cisco": "CSCO",
    "cisco systems": "CSCO",
    "cisco systems inc": "CSCO",
    "cisco systems inc.": "CSCO",
    "webex": "CSCO",

    # ADBE - Adobe Inc.
    "adobe": "ADBE",
    "adobe inc": "ADBE",
    "adobe inc.": "ADBE",
    "photoshop": "ADBE",
    "adobe photoshop": "ADBE",
    "adobe creative cloud": "ADBE",
    "adobe acrobat": "ADBE",
    "adobe firefly": "ADBE",

    # IBM - IBM
    "ibm": "IBM",
    "international business machines": "IBM",
    "big blue": "IBM",
    "red hat": "IBM",
    "ibm watson": "IBM",
    "ibm cloud": "IBM",

    # NFLX - Netflix
    "netflix": "NFLX",
    "netflix inc": "NFLX",
    "netflix inc.": "NFLX",
    "nflx": "NFLX",

    # DELL - Dell Technologies
    "dell": "DELL",
    "dell technologies": "DELL",
    "dell technologies inc": "DELL",

    # INTU - Intuit
    "intuit": "INTU",
    "intuit inc": "INTU",
    "intuit inc.": "INTU",
    "turbotax": "INTU",
    "quickbooks": "INTU",
    "credit karma": "INTU",
    "mailchimp": "INTU",

    # NOW - ServiceNow
    "servicenow": "NOW",
    "servicenow inc": "NOW",

    # PANW - Palo Alto Networks
    "palo alto networks": "PANW",
    "palo alto": "PANW",

    # CRWD - CrowdStrike
    "crowdstrike": "CRWD",
    "crowdstrike holdings": "CRWD",

    # SNPS - Synopsys
    "synopsys": "SNPS",
    "synopsys inc": "SNPS",

    # CDNS - Cadence Design Systems
    "cadence": "CDNS",
    "cadence design": "CDNS",
    "cadence design systems": "CDNS",

    # ADSK - Autodesk
    "autodesk": "ADSK",
    "autodesk inc": "ADSK",
    "autocad": "ADSK",

    # PLTR - Palantir Technologies
    "palantir": "PLTR",
    "palantir technologies": "PLTR",
    "palantir technologies inc": "PLTR",

    # ANET - Arista Networks
    "arista": "ANET",
    "arista networks": "ANET",

    # FTNT - Fortinet
    "fortinet": "FTNT",
    "fortinet inc": "FTNT",

    # WDAY - Workday, Inc.
    "workday": "WDAY",
    "workday inc": "WDAY",
    "workday inc.": "WDAY",

    # DDOG - Datadog
    "datadog": "DDOG",
    "datadog inc": "DDOG",

    # APP - AppLovin
    "applovin": "APP",
    "applovin corp": "APP",

    # SMCI - Supermicro
    "supermicro": "SMCI",
    "super micro computer": "SMCI",
    "super micro": "SMCI",

    # =========================================================================
    # SEMICONDUCTORS
    # =========================================================================

    # QCOM - Qualcomm
    "qualcomm": "QCOM",
    "qualcomm inc": "QCOM",
    "snapdragon": "QCOM",

    # TXN - Texas Instruments
    "texas instruments": "TXN",
    "texas instruments inc": "TXN",

    # MU - Micron Technology
    "micron": "MU",
    "micron technology": "MU",
    "micron technology inc": "MU",

    # LRCX - Lam Research
    "lam research": "LRCX",
    "lam research corp": "LRCX",

    # KLAC - KLA Corporation
    "kla": "KLAC",
    "kla corp": "KLAC",
    "kla corporation": "KLAC",

    # AMAT - Applied Materials
    "applied materials": "AMAT",
    "applied materials inc": "AMAT",

    # NXPI - NXP Semiconductors
    "nxp": "NXPI",
    "nxp semiconductors": "NXPI",

    # MCHP - Microchip Technology
    "microchip": "MCHP",
    "microchip technology": "MCHP",

    # MPWR - Monolithic Power Systems
    "monolithic power": "MPWR",
    "monolithic power systems": "MPWR",

    # ADI - Analog Devices
    "analog devices": "ADI",
    "analog devices inc": "ADI",

    # ON - ON Semiconductor
    "on semiconductor": "ON",
    "on semi": "ON",
    "onsemi": "ON",

    # SWKS - Skyworks Solutions
    "skyworks": "SWKS",
    "skyworks solutions": "SWKS",

    # FSLR - First Solar
    "first solar": "FSLR",
    "first solar inc": "FSLR",

    # TER - Teradyne
    "teradyne": "TER",
    "teradyne inc": "TER",

    # =========================================================================
    # FINANCIALS - BANKS
    # =========================================================================

    # JPM - JPMorgan Chase
    "jpmorgan": "JPM",
    "jpmorgan chase": "JPM",
    "jpmorgan chase & co": "JPM",
    "jpmorgan chase & co.": "JPM",
    "j.p. morgan": "JPM",
    "jp morgan": "JPM",
    "chase": "JPM",
    "chase bank": "JPM",
    "jamie dimon": "JPM",

    # BAC - Bank of America
    "bank of america": "BAC",
    "bank of america corp": "BAC",
    "bofa": "BAC",
    "b of a": "BAC",
    "merrill lynch": "BAC",
    "merrill": "BAC",

    # WFC - Wells Fargo
    "wells fargo": "WFC",
    "wells fargo & co": "WFC",
    "wells fargo & company": "WFC",

    # C - Citigroup
    "citigroup": "C",
    "citigroup inc": "C",
    "citibank": "C",
    "citi": "C",

    # GS - Goldman Sachs
    "goldman sachs": "GS",
    "goldman sachs group": "GS",
    "goldman": "GS",
    "the goldman sachs group": "GS",
    "david solomon": "GS",

    # MS - Morgan Stanley
    "morgan stanley": "MS",
    "morgan stanley & co": "MS",

    # PNC - PNC Financial Services
    "pnc": "PNC",
    "pnc financial": "PNC",
    "pnc financial services": "PNC",

    # USB - U.S. Bancorp
    "u.s. bancorp": "USB",
    "us bancorp": "USB",
    "u.s. bank": "USB",
    "us bank": "USB",

    # TFC - Truist Financial
    "truist": "TFC",
    "truist financial": "TFC",

    # SCHW - Charles Schwab Corporation
    "charles schwab": "SCHW",
    "schwab": "SCHW",
    "the charles schwab corporation": "SCHW",
    "td ameritrade": "SCHW",

    # CFG - Citizens Financial Group
    "citizens financial": "CFG",
    "citizens financial group": "CFG",
    "citizens bank": "CFG",

    # FITB - Fifth Third Bancorp
    "fifth third": "FITB",
    "fifth third bancorp": "FITB",
    "fifth third bank": "FITB",

    # KEY - KeyCorp
    "keycorp": "KEY",
    "keybank": "KEY",

    # HBAN - Huntington Bancshares
    "huntington bancshares": "HBAN",
    "huntington bank": "HBAN",

    # MTB - M&T Bank
    "m&t bank": "MTB",
    "m and t bank": "MTB",

    # RF - Regions Financial Corporation
    "regions financial": "RF",
    "regions bank": "RF",

    # =========================================================================
    # FINANCIALS - INVESTMENT / ASSET MANAGEMENT
    # =========================================================================

    # BRK.B - Berkshire Hathaway
    "berkshire hathaway": "BRK.B",
    "berkshire": "BRK.B",
    "berkshire hathaway inc": "BRK.B",
    "warren buffett": "BRK.B",
    "buffett": "BRK.B",
    "charlie munger": "BRK.B",
    "geico": "BRK.B",

    # BLK - BlackRock
    "blackrock": "BLK",
    "blackrock inc": "BLK",
    "blackrock inc.": "BLK",
    "larry fink": "BLK",
    "ishares": "BLK",

    # BX - Blackstone Inc.
    "blackstone": "BX",
    "blackstone inc": "BX",
    "blackstone inc.": "BX",
    "blackstone group": "BX",

    # KKR - KKR & Co.
    "kkr": "KKR",
    "kkr & co": "KKR",
    "kohlberg kravis roberts": "KKR",

    # APO - Apollo Global Management
    "apollo": "APO",
    "apollo global": "APO",
    "apollo global management": "APO",

    # ARES - Ares Management
    "ares management": "ARES",
    "ares capital": "ARES",

    # SPGI - S&P Global
    "s&p global": "SPGI",
    "s&p global inc": "SPGI",
    "standard & poor's": "SPGI",
    "standard and poor's": "SPGI",
    "standard and poors": "SPGI",

    # MCO - Moody's Corporation
    "moody's": "MCO",
    "moodys": "MCO",
    "moody's corporation": "MCO",
    "moody's corp": "MCO",

    # MSCI - MSCI Inc.
    "msci": "MSCI",
    "msci inc": "MSCI",
    "msci inc.": "MSCI",

    # ICE - Intercontinental Exchange
    "intercontinental exchange": "ICE",
    "ice exchange": "ICE",

    # CME - CME Group
    "cme group": "CME",
    "cme": "CME",
    "chicago mercantile exchange": "CME",

    # NDAQ - Nasdaq, Inc.
    "nasdaq inc": "NDAQ",
    "nasdaq inc.": "NDAQ",
    "the nasdaq": "NDAQ",

    # CBOE - Cboe Global Markets
    "cboe": "CBOE",
    "cboe global markets": "CBOE",

    # TROW - T. Rowe Price
    "t. rowe price": "TROW",
    "t rowe price": "TROW",

    # STT - State Street Corporation
    "state street": "STT",
    "state street corp": "STT",
    "state street corporation": "STT",

    # NTRS - Northern Trust
    "northern trust": "NTRS",
    "northern trust corp": "NTRS",

    # BK - BNY Mellon
    "bny mellon": "BK",
    "bank of new york mellon": "BK",
    "bank of new york": "BK",

    # BEN - Franklin Resources
    "franklin resources": "BEN",
    "franklin templeton": "BEN",

    # IVZ - Invesco
    "invesco": "IVZ",
    "invesco ltd": "IVZ",

    # RJF - Raymond James Financial
    "raymond james": "RJF",
    "raymond james financial": "RJF",

    # IBKR - Interactive Brokers
    "interactive brokers": "IBKR",
    "interactive brokers group": "IBKR",

    # HOOD - Robinhood Markets
    "robinhood": "HOOD",
    "robinhood markets": "HOOD",

    # =========================================================================
    # FINANCIALS - PAYMENTS & FINTECH
    # =========================================================================

    # V - Visa Inc.
    "visa": "V",
    "visa inc": "V",
    "visa inc.": "V",

    # MA - Mastercard
    "mastercard": "MA",
    "mastercard inc": "MA",
    "mastercard inc.": "MA",
    "master card": "MA",

    # PYPL - PayPal
    "paypal": "PYPL",
    "paypal holdings": "PYPL",
    "paypal holdings inc": "PYPL",
    "venmo": "PYPL",

    # XYZ - Block, Inc. (formerly Square)
    "block inc": "XYZ",
    "block inc.": "XYZ",
    "square": "XYZ",
    "square inc": "XYZ",
    "cash app": "XYZ",
    "jack dorsey": "XYZ",

    # AXP - American Express
    "american express": "AXP",
    "amex": "AXP",
    "american express co": "AXP",

    # COF - Capital One
    "capital one": "COF",
    "capital one financial": "COF",

    # SYF - Synchrony Financial
    "synchrony": "SYF",
    "synchrony financial": "SYF",

    # COIN - Coinbase
    "coinbase": "COIN",
    "coinbase global": "COIN",
    "coinbase global inc": "COIN",

    # GPN - Global Payments
    "global payments": "GPN",
    "global payments inc": "GPN",

    # FIS - Fidelity National Information Services
    "fidelity national": "FIS",
    "fidelity national information services": "FIS",
    "fis global": "FIS",
    "worldpay": "FIS",

    # FISV - Fiserv
    "fiserv": "FISV",
    "fiserv inc": "FISV",

    # CPAY - Corpay
    "corpay": "CPAY",
    "fleetcor": "CPAY",

    # =========================================================================
    # FINANCIALS - INSURANCE
    # =========================================================================

    # AIG - American International Group
    "aig": "AIG",
    "american international group": "AIG",

    # MET - MetLife
    "metlife": "MET",
    "metlife inc": "MET",

    # PRU - Prudential Financial
    "prudential": "PRU",
    "prudential financial": "PRU",

    # AFL - Aflac
    "aflac": "AFL",
    "aflac inc": "AFL",

    # ALL - Allstate
    "allstate": "ALL",
    "the allstate corporation": "ALL",
    "allstate corp": "ALL",

    # TRV - Travelers Companies
    "travelers": "TRV",
    "the travelers companies": "TRV",
    "travelers companies": "TRV",

    # PGR - Progressive Corporation
    "progressive": "PGR",
    "progressive corp": "PGR",
    "progressive insurance": "PGR",

    # CB - Chubb Limited
    "chubb": "CB",
    "chubb limited": "CB",
    "chubb ltd": "CB",

    # HIG - Hartford
    "hartford": "HIG",
    "the hartford": "HIG",
    "hartford financial": "HIG",

    # MMC - Marsh McLennan
    "marsh mclennan": "MMC",
    "marsh & mclennan": "MMC",

    # AON - Aon plc
    "aon": "AON",
    "aon plc": "AON",

    # AJG - Arthur J. Gallagher & Co.
    "arthur j. gallagher": "AJG",
    "gallagher": "AJG",
    "aj gallagher": "AJG",

    # WTW - Willis Towers Watson
    "willis towers watson": "WTW",
    "willis towers": "WTW",

    # ACGL - Arch Capital Group
    "arch capital": "ACGL",
    "arch capital group": "ACGL",

    # GL - Globe Life
    "globe life": "GL",
    "globe life inc": "GL",

    # ERIE - Erie Indemnity
    "erie indemnity": "ERIE",
    "erie insurance": "ERIE",

    # CINF - Cincinnati Financial
    "cincinnati financial": "CINF",

    # =========================================================================
    # HEALTHCARE - PHARMA & BIOTECH
    # =========================================================================

    # JNJ - Johnson & Johnson
    "johnson & johnson": "JNJ",
    "johnson and johnson": "JNJ",
    "j&j": "JNJ",
    "jnj": "JNJ",
    "j and j": "JNJ",
    "band-aid": "JNJ",
    "tylenol": "JNJ",

    # UNH - UnitedHealth Group
    "unitedhealth": "UNH",
    "unitedhealth group": "UNH",
    "unitedhealth group inc": "UNH",
    "united health": "UNH",
    "united healthcare": "UNH",
    "unitedhealthcare": "UNH",
    "optum": "UNH",

    # LLY - Lilly (Eli)
    "eli lilly": "LLY",
    "eli lilly and company": "LLY",
    "eli lilly & co": "LLY",
    "lilly": "LLY",
    "mounjaro": "LLY",
    "zepbound": "LLY",

    # MRK - Merck & Co.
    "merck": "MRK",
    "merck & co": "MRK",
    "merck & co.": "MRK",
    "merck and co": "MRK",
    "keytruda": "MRK",

    # ABBV - AbbVie
    "abbvie": "ABBV",
    "abbvie inc": "ABBV",
    "abbvie inc.": "ABBV",
    "humira": "ABBV",
    "skyrizi": "ABBV",

    # PFE - Pfizer
    "pfizer": "PFE",
    "pfizer inc": "PFE",
    "pfizer inc.": "PFE",
    "paxlovid": "PFE",

    # TMO - Thermo Fisher Scientific
    "thermo fisher": "TMO",
    "thermo fisher scientific": "TMO",
    "thermo fisher scientific inc": "TMO",

    # ABT - Abbott Laboratories
    "abbott": "ABT",
    "abbott laboratories": "ABT",
    "abbott labs": "ABT",

    # BMY - Bristol Myers Squibb
    "bristol-myers squibb": "BMY",
    "bristol myers squibb": "BMY",
    "bristol-myers": "BMY",
    "bristol myers": "BMY",
    "bms": "BMY",

    # AMGN - Amgen
    "amgen": "AMGN",
    "amgen inc": "AMGN",
    "amgen inc.": "AMGN",

    # GILD - Gilead Sciences
    "gilead": "GILD",
    "gilead sciences": "GILD",
    "gilead sciences inc": "GILD",

    # MDT - Medtronic
    "medtronic": "MDT",
    "medtronic plc": "MDT",

    # ISRG - Intuitive Surgical
    "intuitive surgical": "ISRG",
    "intuitive surgical inc": "ISRG",
    "da vinci surgical": "ISRG",

    # VRTX - Vertex Pharmaceuticals
    "vertex": "VRTX",
    "vertex pharmaceuticals": "VRTX",
    "vertex pharma": "VRTX",

    # REGN - Regeneron Pharmaceuticals
    "regeneron": "REGN",
    "regeneron pharmaceuticals": "REGN",

    # SYK - Stryker Corporation
    "stryker": "SYK",
    "stryker corp": "SYK",
    "stryker corporation": "SYK",

    # BSX - Boston Scientific
    "boston scientific": "BSX",
    "boston scientific corp": "BSX",

    # BDX - Becton Dickinson
    "becton dickinson": "BDX",
    "bd medical": "BDX",

    # ELV - Elevance Health
    "elevance health": "ELV",
    "elevance": "ELV",
    "anthem": "ELV",
    "anthem inc": "ELV",

    # CI - Cigna
    "cigna": "CI",
    "cigna group": "CI",
    "the cigna group": "CI",

    # HUM - Humana
    "humana": "HUM",
    "humana inc": "HUM",

    # CNC - Centene Corporation
    "centene": "CNC",
    "centene corp": "CNC",
    "centene corporation": "CNC",

    # MOH - Molina Healthcare
    "molina healthcare": "MOH",
    "molina": "MOH",

    # HCA - HCA Healthcare
    "hca healthcare": "HCA",
    "hca": "HCA",

    # CVS - CVS Health
    "cvs health": "CVS",
    "cvs": "CVS",
    "cvs pharmacy": "CVS",
    "cvs caremark": "CVS",
    "aetna": "CVS",

    # MCK - McKesson Corporation
    "mckesson": "MCK",
    "mckesson corp": "MCK",
    "mckesson corporation": "MCK",

    # MRNA - Moderna
    "moderna": "MRNA",
    "moderna inc": "MRNA",

    # BIIB - Biogen
    "biogen": "BIIB",
    "biogen inc": "BIIB",

    # INCY - Incyte
    "incyte": "INCY",
    "incyte corp": "INCY",

    # DXCM - Dexcom
    "dexcom": "DXCM",
    "dexcom inc": "DXCM",

    # IDXX - Idexx Laboratories
    "idexx": "IDXX",
    "idexx laboratories": "IDXX",

    # DHR - Danaher Corporation
    "danaher": "DHR",
    "danaher corp": "DHR",
    "danaher corporation": "DHR",

    # IQV - IQVIA
    "iqvia": "IQV",
    "iqvia holdings": "IQV",

    # ZBH - Zimmer Biomet
    "zimmer biomet": "ZBH",
    "zimmer biomet holdings": "ZBH",

    # GEHC - GE HealthCare
    "ge healthcare": "GEHC",
    "ge health care": "GEHC",

    # ZTS - Zoetis
    "zoetis": "ZTS",
    "zoetis inc": "ZTS",

    # KVUE - Kenvue
    "kenvue": "KVUE",
    "kenvue inc": "KVUE",

    # ALGN - Align Technology
    "align technology": "ALGN",
    "invisalign": "ALGN",

    # SOLV - Solventum
    "solventum": "SOLV",
    "solventum corp": "SOLV",

    # =========================================================================
    # CONSUMER STAPLES
    # =========================================================================

    # WMT - Walmart
    "walmart": "WMT",
    "walmart inc": "WMT",
    "walmart inc.": "WMT",
    "wal-mart": "WMT",
    "sam's club": "WMT",

    # PG - Procter & Gamble
    "procter & gamble": "PG",
    "procter and gamble": "PG",
    "p&g": "PG",
    "procter gamble": "PG",
    "tide": "PG",

    # KO - Coca-Cola Company
    "coca-cola": "KO",
    "coca cola": "KO",
    "the coca-cola company": "KO",
    "coke": "KO",

    # PEP - PepsiCo
    "pepsico": "PEP",
    "pepsi": "PEP",
    "pepsico inc": "PEP",
    "frito-lay": "PEP",
    "frito lay": "PEP",
    "gatorade": "PEP",
    "lay's": "PEP",
    "doritos": "PEP",

    # COST - Costco
    "costco": "COST",
    "costco wholesale": "COST",
    "costco wholesale corp": "COST",

    # MDLZ - Mondelez International
    "mondelez": "MDLZ",
    "mondelez international": "MDLZ",
    "oreo": "MDLZ",
    "cadbury": "MDLZ",

    # CL - Colgate-Palmolive
    "colgate-palmolive": "CL",
    "colgate palmolive": "CL",
    "colgate": "CL",

    # KMB - Kimberly-Clark
    "kimberly-clark": "KMB",
    "kimberly clark": "KMB",
    "kleenex": "KMB",
    "huggies": "KMB",

    # KHC - Kraft Heinz
    "kraft heinz": "KHC",
    "the kraft heinz company": "KHC",
    "kraft": "KHC",
    "heinz": "KHC",

    # GIS - General Mills
    "general mills": "GIS",
    "general mills inc": "GIS",
    "cheerios": "GIS",

    # SYY - Sysco
    "sysco": "SYY",
    "sysco corp": "SYY",
    "sysco corporation": "SYY",

    # KR - Kroger
    "kroger": "KR",
    "the kroger co": "KR",
    "kroger co": "KR",

    # HSY - Hershey Company
    "hershey": "HSY",
    "the hershey company": "HSY",
    "hershey's": "HSY",

    # MKC - McCormick & Company
    "mccormick": "MKC",
    "mccormick & company": "MKC",
    "mccormick and company": "MKC",

    # KDP - Keurig Dr Pepper
    "keurig dr pepper": "KDP",
    "keurig": "KDP",
    "dr pepper": "KDP",

    # CLX - Clorox
    "clorox": "CLX",
    "the clorox company": "CLX",

    # CAG - Conagra Brands
    "conagra": "CAG",
    "conagra brands": "CAG",

    # TSN - Tyson Foods
    "tyson foods": "TSN",
    "tyson": "TSN",

    # HRL - Hormel Foods
    "hormel": "HRL",
    "hormel foods": "HRL",
    "spam": "HRL",

    # ADM - Archer Daniels Midland
    "archer daniels midland": "ADM",
    "archer-daniels-midland": "ADM",
    "adm": "ADM",

    # STZ - Constellation Brands
    "constellation brands": "STZ",
    "corona beer": "STZ",
    "modelo": "STZ",

    # TAP - Molson Coors
    "molson coors": "TAP",
    "molson coors beverage": "TAP",
    "coors": "TAP",

    # MO - Altria
    "altria": "MO",
    "altria group": "MO",
    "marlboro": "MO",
    "philip morris domestic": "MO",

    # PM - Philip Morris International
    "philip morris": "PM",
    "philip morris international": "PM",
    "iqos": "PM",

    # BG - Bunge Global
    "bunge": "BG",
    "bunge global": "BG",

    # EL - Estee Lauder
    "estee lauder": "EL",
    "estee lauder companies": "EL",
    "the estee lauder companies": "EL",

    # CHD - Church & Dwight
    "church & dwight": "CHD",
    "church and dwight": "CHD",
    "arm & hammer": "CHD",
    "oxiclean": "CHD",

    # MNST - Monster Beverage
    "monster beverage": "MNST",
    "monster energy": "MNST",

    # DG - Dollar General
    "dollar general": "DG",
    "dollar general corp": "DG",

    # DLTR - Dollar Tree
    "dollar tree": "DLTR",
    "dollar tree inc": "DLTR",

    # TGT - Target Corporation
    "target": "TGT",
    "target corp": "TGT",
    "target corporation": "TGT",

    # LW - Lamb Weston
    "lamb weston": "LW",
    "lamb weston holdings": "LW",

    # =========================================================================
    # CONSUMER DISCRETIONARY
    # =========================================================================

    # MCD - McDonald's
    "mcdonald's": "MCD",
    "mcdonalds": "MCD",
    "mcdonald's corp": "MCD",
    "micky d's": "MCD",

    # NKE - Nike, Inc.
    "nike": "NKE",
    "nike inc": "NKE",
    "nike inc.": "NKE",
    "jordan brand": "NKE",
    "air jordan": "NKE",

    # SBUX - Starbucks
    "starbucks": "SBUX",
    "starbucks corp": "SBUX",
    "starbucks corporation": "SBUX",

    # HD - Home Depot
    "home depot": "HD",
    "the home depot": "HD",
    "home depot inc": "HD",

    # LOW - Lowe's
    "lowe's": "LOW",
    "lowes": "LOW",
    "lowe's companies": "LOW",

    # BKNG - Booking Holdings
    "booking holdings": "BKNG",
    "booking.com": "BKNG",
    "priceline": "BKNG",
    "kayak": "BKNG",

    # CMG - Chipotle Mexican Grill
    "chipotle": "CMG",
    "chipotle mexican grill": "CMG",

    # MAR - Marriott International
    "marriott": "MAR",
    "marriott international": "MAR",

    # HLT - Hilton Worldwide
    "hilton": "HLT",
    "hilton worldwide": "HLT",
    "hilton hotels": "HLT",

    # ABNB - Airbnb
    "airbnb": "ABNB",
    "airbnb inc": "ABNB",

    # UBER - Uber
    "uber": "UBER",
    "uber technologies": "UBER",
    "uber eats": "UBER",

    # DASH - DoorDash
    "doordash": "DASH",
    "doordash inc": "DASH",

    # LULU - Lululemon Athletica
    "lululemon": "LULU",
    "lululemon athletica": "LULU",
    "lulu": "LULU",

    # ROST - Ross Stores
    "ross stores": "ROST",
    "ross dress for less": "ROST",

    # TJX - TJX Companies
    "tjx": "TJX",
    "tjx companies": "TJX",
    "tj maxx": "TJX",
    "t.j. maxx": "TJX",
    "marshalls": "TJX",
    "homegoods": "TJX",

    # GM - General Motors
    "general motors": "GM",
    "general motors co": "GM",
    "gm": "GM",
    "chevrolet": "GM",
    "chevy": "GM",
    "cadillac": "GM",
    "gmc": "GM",
    "buick": "GM",

    # F - Ford Motor Company
    "ford": "F",
    "ford motor": "F",
    "ford motor company": "F",
    "ford motor co": "F",

    # TSCO - Tractor Supply
    "tractor supply": "TSCO",
    "tractor supply co": "TSCO",

    # EBAY - eBay Inc.
    "ebay": "EBAY",
    "ebay inc": "EBAY",
    "ebay inc.": "EBAY",

    # ORLY - O'Reilly Automotive
    "o'reilly automotive": "ORLY",
    "o'reilly auto parts": "ORLY",
    "oreilly automotive": "ORLY",

    # AZO - AutoZone
    "autozone": "AZO",
    "auto zone": "AZO",

    # RCL - Royal Caribbean Group
    "royal caribbean": "RCL",
    "royal caribbean group": "RCL",

    # CCL - Carnival
    "carnival": "CCL",
    "carnival corp": "CCL",
    "carnival cruise": "CCL",
    "carnival corporation": "CCL",

    # NCLH - Norwegian Cruise Line
    "norwegian cruise line": "NCLH",
    "norwegian cruise": "NCLH",

    # LVS - Las Vegas Sands
    "las vegas sands": "LVS",
    "las vegas sands corp": "LVS",

    # WYNN - Wynn Resorts
    "wynn resorts": "WYNN",
    "wynn": "WYNN",

    # MGM - MGM Resorts
    "mgm resorts": "MGM",
    "mgm resorts international": "MGM",
    "mgm": "MGM",

    # DPZ - Domino's
    "domino's": "DPZ",
    "dominos": "DPZ",
    "domino's pizza": "DPZ",

    # DRI - Darden Restaurants
    "darden restaurants": "DRI",
    "darden": "DRI",
    "olive garden": "DRI",

    # YUM - Yum! Brands
    "yum brands": "YUM",
    "yum! brands": "YUM",
    "taco bell": "YUM",
    "kfc": "YUM",
    "pizza hut": "YUM",

    # ULTA - Ulta Beauty
    "ulta beauty": "ULTA",
    "ulta": "ULTA",

    # DHI - D. R. Horton
    "d.r. horton": "DHI",
    "dr horton": "DHI",
    "d. r. horton": "DHI",

    # LEN - Lennar
    "lennar": "LEN",
    "lennar corp": "LEN",

    # NVR - NVR, Inc.
    "nvr inc": "NVR",

    # PHM - PulteGroup
    "pultegroup": "PHM",
    "pulte group": "PHM",
    "pulte homes": "PHM",

    # GRMN - Garmin
    "garmin": "GRMN",
    "garmin ltd": "GRMN",

    # HAS - Hasbro
    "hasbro": "HAS",
    "hasbro inc": "HAS",

    # BBY - Best Buy
    "best buy": "BBY",
    "best buy co": "BBY",

    # TPR - Tapestry, Inc.
    "tapestry": "TPR",
    "tapestry inc": "TPR",
    "coach": "TPR",
    "kate spade": "TPR",

    # RL - Ralph Lauren
    "ralph lauren": "RL",
    "ralph lauren corp": "RL",
    "polo ralph lauren": "RL",

    # DECK - Deckers Brands
    "deckers brands": "DECK",
    "deckers": "DECK",
    "ugg": "DECK",
    "hoka": "DECK",

    # APTV - Aptiv
    "aptiv": "APTV",
    "aptiv plc": "APTV",
    "delphi": "APTV",

    # EXPE - Expedia Group
    "expedia": "EXPE",
    "expedia group": "EXPE",
    "vrbo": "EXPE",
    "hotels.com": "EXPE",

    # MTCH - Match Group
    "match group": "MTCH",
    "tinder": "MTCH",
    "hinge": "MTCH",

    # POOL - Pool Corporation
    "pool corp": "POOL",
    "pool corporation": "POOL",

    # =========================================================================
    # ENERGY
    # =========================================================================

    # XOM - ExxonMobil
    "exxonmobil": "XOM",
    "exxon mobil": "XOM",
    "exxon": "XOM",
    "exxon mobil corporation": "XOM",
    "exxon mobil corp": "XOM",
    "mobil": "XOM",

    # CVX - Chevron Corporation
    "chevron": "CVX",
    "chevron corp": "CVX",
    "chevron corporation": "CVX",

    # COP - ConocoPhillips
    "conocophillips": "COP",
    "conoco phillips": "COP",
    "conoco": "COP",

    # SLB - Schlumberger
    "schlumberger": "SLB",
    "schlumberger ltd": "SLB",
    "slb": "SLB",

    # EOG - EOG Resources
    "eog resources": "EOG",
    "eog": "EOG",

    # MPC - Marathon Petroleum
    "marathon petroleum": "MPC",
    "marathon petroleum corp": "MPC",

    # PSX - Phillips 66
    "phillips 66": "PSX",

    # VLO - Valero Energy
    "valero": "VLO",
    "valero energy": "VLO",
    "valero energy corp": "VLO",

    # OXY - Occidental Petroleum
    "occidental petroleum": "OXY",
    "occidental": "OXY",
    "oxy": "OXY",

    # DVN - Devon Energy
    "devon energy": "DVN",
    "devon": "DVN",

    # FANG - Diamondback Energy
    "diamondback energy": "FANG",
    "diamondback": "FANG",

    # HAL - Halliburton
    "halliburton": "HAL",
    "halliburton co": "HAL",

    # BKR - Baker Hughes
    "baker hughes": "BKR",
    "baker hughes co": "BKR",

    # KMI - Kinder Morgan
    "kinder morgan": "KMI",
    "kinder morgan inc": "KMI",

    # WMB - Williams Companies
    "williams companies": "WMB",
    "the williams companies": "WMB",
    "williams cos": "WMB",

    # OKE - Oneok
    "oneok": "OKE",
    "oneok inc": "OKE",

    # TRGP - Targa Resources
    "targa resources": "TRGP",
    "targa": "TRGP",

    # CTRA - Coterra
    "coterra": "CTRA",
    "coterra energy": "CTRA",

    # EQT - EQT Corporation
    "eqt": "EQT",
    "eqt corp": "EQT",
    "eqt corporation": "EQT",

    # TPL - Texas Pacific Land
    "texas pacific land": "TPL",

    # APA - APA Corporation
    "apa corporation": "APA",
    "apa corp": "APA",
    "apache": "APA",
    "apache corp": "APA",

    # =========================================================================
    # INDUSTRIALS
    # =========================================================================

    # BA - Boeing
    "boeing": "BA",
    "boeing co": "BA",
    "the boeing company": "BA",
    "boeing company": "BA",
    "boeing 737": "BA",
    "boeing 787": "BA",

    # CAT - Caterpillar Inc.
    "caterpillar": "CAT",
    "caterpillar inc": "CAT",
    "caterpillar inc.": "CAT",

    # HON - Honeywell
    "honeywell": "HON",
    "honeywell international": "HON",
    "honeywell international inc": "HON",

    # UPS - United Parcel Service
    "ups": "UPS",
    "united parcel service": "UPS",
    "united parcel": "UPS",

    # GE - GE Aerospace
    "ge aerospace": "GE",
    "general electric": "GE",

    # GEV - GE Vernova
    "ge vernova": "GEV",

    # RTX - RTX Corporation
    "rtx": "RTX",
    "rtx corporation": "RTX",
    "rtx corp": "RTX",
    "raytheon": "RTX",
    "raytheon technologies": "RTX",
    "pratt & whitney": "RTX",
    "pratt and whitney": "RTX",
    "collins aerospace": "RTX",

    # LMT - Lockheed Martin
    "lockheed martin": "LMT",
    "lockheed martin corp": "LMT",
    "lockheed": "LMT",

    # DE - Deere & Company
    "deere": "DE",
    "deere & company": "DE",
    "john deere": "DE",

    # MMM - 3M
    "3m": "MMM",
    "3m company": "MMM",
    "3m co": "MMM",

    # NOC - Northrop Grumman
    "northrop grumman": "NOC",
    "northrop grumman corp": "NOC",

    # GD - General Dynamics
    "general dynamics": "GD",
    "general dynamics corp": "GD",

    # LHX - L3Harris
    "l3harris": "LHX",
    "l3 harris": "LHX",
    "l3harris technologies": "LHX",
    "harris corporation": "LHX",

    # HII - Huntington Ingalls Industries
    "huntington ingalls": "HII",
    "huntington ingalls industries": "HII",

    # TDG - TransDigm Group
    "transdigm": "TDG",
    "transdigm group": "TDG",

    # HWM - Howmet Aerospace
    "howmet aerospace": "HWM",
    "howmet": "HWM",

    # AXON - Axon Enterprise
    "axon": "AXON",
    "axon enterprise": "AXON",
    "taser": "AXON",

    # TXT - Textron
    "textron": "TXT",
    "textron inc": "TXT",
    "bell helicopter": "TXT",
    "cessna": "TXT",

    # FDX - FedEx
    "fedex": "FDX",
    "fed ex": "FDX",
    "federal express": "FDX",
    "fedex corp": "FDX",

    # NSC - Norfolk Southern
    "norfolk southern": "NSC",
    "norfolk southern corp": "NSC",

    # UNP - Union Pacific Corporation
    "union pacific": "UNP",
    "union pacific corp": "UNP",
    "union pacific railroad": "UNP",

    # CSX - CSX Corporation
    "csx": "CSX",
    "csx corp": "CSX",
    "csx corporation": "CSX",

    # DAL - Delta Air Lines
    "delta air lines": "DAL",
    "delta airlines": "DAL",
    "delta": "DAL",

    # UAL - United Airlines Holdings
    "united airlines": "UAL",
    "united airlines holdings": "UAL",

    # LUV - Southwest Airlines
    "southwest airlines": "LUV",
    "southwest": "LUV",
    "southwest air": "LUV",

    # WM - Waste Management
    "waste management": "WM",
    "waste management inc": "WM",

    # RSG - Republic Services
    "republic services": "RSG",
    "republic services inc": "RSG",

    # EMR - Emerson Electric
    "emerson": "EMR",
    "emerson electric": "EMR",
    "emerson electric co": "EMR",

    # ETN - Eaton Corporation
    "eaton": "ETN",
    "eaton corp": "ETN",
    "eaton corporation": "ETN",

    # ITW - Illinois Tool Works
    "illinois tool works": "ITW",
    "itw": "ITW",

    # PH - Parker Hannifin
    "parker hannifin": "PH",
    "parker-hannifin": "PH",

    # CMI - Cummins
    "cummins": "CMI",
    "cummins inc": "CMI",

    # ROK - Rockwell Automation
    "rockwell automation": "ROK",
    "rockwell": "ROK",

    # PCAR - Paccar
    "paccar": "PCAR",
    "paccar inc": "PCAR",
    "kenworth": "PCAR",
    "peterbilt": "PCAR",

    # CARR - Carrier Global
    "carrier global": "CARR",
    "carrier": "CARR",

    # OTIS - Otis Worldwide
    "otis": "OTIS",
    "otis worldwide": "OTIS",
    "otis elevator": "OTIS",

    # TT - Trane Technologies
    "trane technologies": "TT",
    "trane": "TT",

    # IR - Ingersoll Rand
    "ingersoll rand": "IR",
    "ingersoll-rand": "IR",

    # ADP - Automatic Data Processing
    "adp": "ADP",
    "automatic data processing": "ADP",

    # PAYX - Paychex
    "paychex": "PAYX",
    "paychex inc": "PAYX",

    # CTAS - Cintas
    "cintas": "CTAS",
    "cintas corp": "CTAS",

    # URI - United Rentals
    "united rentals": "URI",
    "united rentals inc": "URI",

    # EFX - Equifax
    "equifax": "EFX",
    "equifax inc": "EFX",

    # VRSK - Verisk Analytics
    "verisk": "VRSK",
    "verisk analytics": "VRSK",

    # WAB - Wabtec
    "wabtec": "WAB",
    "westinghouse air brake": "WAB",

    # ODFL - Old Dominion
    "old dominion": "ODFL",
    "old dominion freight": "ODFL",
    "old dominion freight line": "ODFL",

    # JBHT - J.B. Hunt
    "j.b. hunt": "JBHT",
    "jb hunt": "JBHT",
    "j.b. hunt transport": "JBHT",

    # CHRW - C.H. Robinson
    "c.h. robinson": "CHRW",
    "ch robinson": "CHRW",

    # EXPD - Expeditors International
    "expeditors": "EXPD",
    "expeditors international": "EXPD",

    # LDOS - Leidos
    "leidos": "LDOS",
    "leidos holdings": "LDOS",

    # ACN - Accenture
    "accenture": "ACN",
    "accenture plc": "ACN",

    # SWK - Stanley Black & Decker
    "stanley black & decker": "SWK",
    "stanley black and decker": "SWK",

    # SNA - Snap-on
    "snap-on": "SNA",
    "snap on": "SNA",
    "snapon": "SNA",

    # PWR - Quanta Services
    "quanta services": "PWR",
    "quanta": "PWR",

    # EME - Emcor
    "emcor": "EME",
    "emcor group": "EME",

    # DOV - Dover Corporation
    "dover": "DOV",
    "dover corp": "DOV",

    # GNRC - Generac
    "generac": "GNRC",
    "generac holdings": "GNRC",

    # FAST - Fastenal
    "fastenal": "FAST",
    "fastenal company": "FAST",

    # BLDR - Builders FirstSource
    "builders firstsource": "BLDR",
    "builders first source": "BLDR",

    # GWW - W. W. Grainger
    "grainger": "GWW",
    "w.w. grainger": "GWW",
    "w. w. grainger": "GWW",

    # CPRT - Copart
    "copart": "CPRT",
    "copart inc": "CPRT",

    # =========================================================================
    # COMMUNICATION SERVICES & MEDIA
    # =========================================================================

    # DIS - Walt Disney Company
    "disney": "DIS",
    "walt disney": "DIS",
    "the walt disney company": "DIS",
    "walt disney company": "DIS",
    "disney+": "DIS",
    "disney plus": "DIS",
    "hulu": "DIS",
    "espn": "DIS",
    "marvel studios": "DIS",
    "pixar": "DIS",
    "star wars": "DIS",
    "disneyland": "DIS",
    "disney world": "DIS",

    # CMCSA - Comcast
    "comcast": "CMCSA",
    "comcast corp": "CMCSA",
    "comcast corporation": "CMCSA",
    "nbcuniversal": "CMCSA",
    "nbc": "CMCSA",
    "universal studios": "CMCSA",
    "peacock streaming": "CMCSA",
    "xfinity": "CMCSA",

    # T - AT&T
    "at&t": "T",
    "at&t inc": "T",
    "att": "T",
    "at and t": "T",

    # VZ - Verizon
    "verizon": "VZ",
    "verizon communications": "VZ",
    "verizon wireless": "VZ",

    # TMUS - T-Mobile US
    "t-mobile": "TMUS",
    "t mobile": "TMUS",
    "tmobile": "TMUS",
    "t-mobile us": "TMUS",

    # CHTR - Charter Communications
    "charter communications": "CHTR",
    "charter": "CHTR",
    "spectrum": "CHTR",

    # PSKY - Paramount Skydance Corporation
    "paramount": "PSKY",
    "paramount global": "PSKY",
    "paramount skydance": "PSKY",
    "paramount pictures": "PSKY",
    "cbs": "PSKY",
    "paramount+": "PSKY",
    "paramount plus": "PSKY",

    # WBD - Warner Bros. Discovery
    "warner bros. discovery": "WBD",
    "warner bros discovery": "WBD",
    "warner brothers": "WBD",
    "warner media": "WBD",
    "hbo": "WBD",
    "hbo max": "WBD",
    "max streaming": "WBD",
    "cnn": "WBD",
    "discovery": "WBD",

    # NWSA / NWS - News Corp
    "news corp": "NWSA",
    "news corporation": "NWSA",
    "wall street journal": "NWSA",
    "wsj": "NWSA",
    "dow jones": "NWSA",
    "fox news": "FOXA",

    # FOXA / FOX - Fox Corporation
    "fox corporation": "FOXA",
    "fox corp": "FOXA",
    "fox business": "FOXA",
    "fox sports": "FOXA",

    # EA - Electronic Arts
    "electronic arts": "EA",
    "ea sports": "EA",
    "ea games": "EA",

    # TTWO - Take-Two Interactive
    "take-two interactive": "TTWO",
    "take two interactive": "TTWO",
    "take-two": "TTWO",
    "rockstar games": "TTWO",
    "gta": "TTWO",
    "grand theft auto": "TTWO",
    "2k games": "TTWO",

    # LYV - Live Nation Entertainment
    "live nation": "LYV",
    "live nation entertainment": "LYV",
    "ticketmaster": "LYV",

    # OMC - Omnicom Group
    "omnicom": "OMC",
    "omnicom group": "OMC",

    # TTD - Trade Desk
    "the trade desk": "TTD",
    "trade desk": "TTD",

    # TKO - TKO Group Holdings
    "tko group": "TKO",
    "tko": "TKO",
    "wwe": "TKO",
    "ufc": "TKO",

    # =========================================================================
    # REAL ESTATE
    # =========================================================================

    # PLD - Prologis
    "prologis": "PLD",
    "prologis inc": "PLD",

    # AMT - American Tower
    "american tower": "AMT",
    "american tower corp": "AMT",

    # CCI - Crown Castle
    "crown castle": "CCI",
    "crown castle international": "CCI",

    # EQIX - Equinix
    "equinix": "EQIX",
    "equinix inc": "EQIX",

    # DLR - Digital Realty
    "digital realty": "DLR",
    "digital realty trust": "DLR",

    # PSA - Public Storage
    "public storage": "PSA",

    # SPG - Simon Property Group
    "simon property group": "SPG",
    "simon property": "SPG",

    # WELL - Welltower
    "welltower": "WELL",
    "welltower inc": "WELL",

    # VICI - Vici Properties
    "vici properties": "VICI",
    "vici": "VICI",

    # CBRE - CBRE Group
    "cbre": "CBRE",
    "cbre group": "CBRE",

    # IRM - Iron Mountain
    "iron mountain": "IRM",
    "iron mountain inc": "IRM",

    # SBAC - SBA Communications
    "sba communications": "SBAC",

    # AVB - AvalonBay Communities
    "avalonbay": "AVB",
    "avalonbay communities": "AVB",

    # EQR - Equity Residential
    "equity residential": "EQR",

    # ARE - Alexandria Real Estate
    "alexandria real estate": "ARE",
    "alexandria real estate equities": "ARE",

    # INVH - Invitation Homes
    "invitation homes": "INVH",

    # EXR - Extra Space Storage
    "extra space storage": "EXR",

    # CSGP - CoStar Group
    "costar": "CSGP",
    "costar group": "CSGP",

    # =========================================================================
    # UTILITIES
    # =========================================================================

    # NEE - NextEra Energy
    "nextera energy": "NEE",
    "nextera": "NEE",
    "florida power & light": "NEE",

    # SO - Southern Company
    "southern company": "SO",
    "the southern company": "SO",
    "southern co": "SO",

    # DUK - Duke Energy
    "duke energy": "DUK",
    "duke energy corp": "DUK",

    # CEG - Constellation Energy
    "constellation energy": "CEG",
    "constellation": "CEG",

    # AEP - American Electric Power
    "american electric power": "AEP",

    # EXC - Exelon
    "exelon": "EXC",
    "exelon corp": "EXC",

    # SRE - Sempra
    "sempra": "SRE",
    "sempra energy": "SRE",

    # PCG - PG&E Corporation
    "pg&e": "PCG",
    "pge": "PCG",
    "pacific gas and electric": "PCG",
    "pacific gas & electric": "PCG",

    # ED - Consolidated Edison
    "con edison": "ED",
    "consolidated edison": "ED",
    "con ed": "ED",

    # VST - Vistra Corp.
    "vistra": "VST",
    "vistra corp": "VST",
    "vistra energy": "VST",

    # XEL - Xcel Energy
    "xcel energy": "XEL",
    "xcel": "XEL",

    # WEC - WEC Energy Group
    "wec energy": "WEC",
    "wec energy group": "WEC",

    # ETR - Entergy
    "entergy": "ETR",
    "entergy corp": "ETR",

    # DTE - DTE Energy
    "dte energy": "DTE",
    "dte": "DTE",

    # EIX - Edison International
    "edison international": "EIX",
    "southern california edison": "EIX",

    # PPL - PPL Corporation
    "ppl": "PPL",
    "ppl corp": "PPL",
    "ppl corporation": "PPL",

    # NRG - NRG Energy
    "nrg energy": "NRG",
    "nrg": "NRG",

    # AES - AES Corporation
    "aes": "AES",
    "aes corp": "AES",
    "aes corporation": "AES",

    # =========================================================================
    # MATERIALS
    # =========================================================================

    # LIN - Linde plc
    "linde": "LIN",
    "linde plc": "LIN",

    # APD - Air Products
    "air products": "APD",
    "air products and chemicals": "APD",

    # SHW - Sherwin-Williams
    "sherwin-williams": "SHW",
    "sherwin williams": "SHW",
    "the sherwin-williams company": "SHW",

    # ECL - Ecolab
    "ecolab": "ECL",
    "ecolab inc": "ECL",

    # FCX - Freeport-McMoRan
    "freeport-mcmoran": "FCX",
    "freeport mcmoran": "FCX",
    "freeport": "FCX",

    # NEM - Newmont
    "newmont": "NEM",
    "newmont corp": "NEM",
    "newmont mining": "NEM",

    # NUE - Nucor
    "nucor": "NUE",
    "nucor corp": "NUE",

    # DOW - Dow Inc.
    "dow": "DOW",
    "dow inc": "DOW",
    "dow chemical": "DOW",
    "dow inc.": "DOW",

    # DD - DuPont
    "dupont": "DD",
    "dupont de nemours": "DD",

    # PPG - PPG Industries
    "ppg": "PPG",
    "ppg industries": "PPG",

    # CTVA - Corteva
    "corteva": "CTVA",
    "corteva agriscience": "CTVA",

    # VMC - Vulcan Materials
    "vulcan materials": "VMC",
    "vulcan materials company": "VMC",

    # MLM - Martin Marietta Materials
    "martin marietta": "MLM",
    "martin marietta materials": "MLM",

    # CF - CF Industries
    "cf industries": "CF",
    "cf industries holdings": "CF",

    # ALB - Albemarle
    "albemarle": "ALB",
    "albemarle corp": "ALB",

    # IFF - International Flavors & Fragrances
    "iff": "IFF",
    "international flavors & fragrances": "IFF",
    "international flavors and fragrances": "IFF",

    # IP - International Paper
    "international paper": "IP",
    "international paper co": "IP",

    # LYB - LyondellBasell
    "lyondellbasell": "LYB",
    "lyondell basell": "LYB",

    # AVY - Avery Dennison
    "avery dennison": "AVY",
    "avery dennison corp": "AVY",

    # BALL - Ball Corporation
    "ball corp": "BALL",
    "ball corporation": "BALL",

    # STLD - Steel Dynamics
    "steel dynamics": "STLD",
    "steel dynamics inc": "STLD",

    # MOS - Mosaic Company
    "mosaic": "MOS",
    "the mosaic company": "MOS",

    # AMCR - Amcor
    "amcor": "AMCR",
    "amcor plc": "AMCR",

    # =========================================================================
    # OTHER NOTABLE COMPANIES
    # =========================================================================

    # SNOW - Snowflake (if in S&P 500 by Feb 2026, include)
    # Note: Snowflake may not be in S&P 500 as of this dataset

    # CTSH - Cognizant
    "cognizant": "CTSH",
    "cognizant technology solutions": "CTSH",

    # EPAM - EPAM Systems
    "epam": "EPAM",
    "epam systems": "EPAM",

    # HPE - Hewlett Packard Enterprise
    "hewlett packard enterprise": "HPE",
    "hpe": "HPE",

    # HPQ - HP Inc.
    "hp inc": "HPQ",
    "hp inc.": "HPQ",
    "hewlett-packard": "HPQ",
    "hewlett packard": "HPQ",

    # GLW - Corning Inc.
    "corning": "GLW",
    "corning inc": "GLW",
    "corning inc.": "GLW",
    "gorilla glass": "GLW",

    # APH - Amphenol
    "amphenol": "APH",
    "amphenol corp": "APH",

    # TEL - TE Connectivity
    "te connectivity": "TEL",

    # MSI - Motorola Solutions
    "motorola solutions": "MSI",
    "motorola": "MSI",

    # VRSN - Verisign
    "verisign": "VRSN",
    "verisign inc": "VRSN",

    # AKAM - Akamai Technologies
    "akamai": "AKAM",
    "akamai technologies": "AKAM",

    # GDDY - GoDaddy
    "godaddy": "GDDY",
    "godaddy inc": "GDDY",

    # FICO - Fair Isaac
    "fair isaac": "FICO",
    "fico": "FICO",
    "fico score": "FICO",

    # BR - Broadridge Financial Solutions
    "broadridge": "BR",
    "broadridge financial": "BR",

    # CDW - CDW Corporation
    "cdw": "CDW",
    "cdw corp": "CDW",

    # NTAP - NetApp
    "netapp": "NTAP",
    "net app": "NTAP",

    # STX - Seagate Technology
    "seagate": "STX",
    "seagate technology": "STX",

    # WDC - Western Digital
    "western digital": "WDC",
    "western digital corp": "WDC",

    # SNDK - Sandisk
    "sandisk": "SNDK",

    # JBL - Jabil
    "jabil": "JBL",
    "jabil inc": "JBL",

    # ROP - Roper Technologies
    "roper technologies": "ROP",
    "roper": "ROP",

    # TRMB - Trimble Inc.
    "trimble": "TRMB",
    "trimble inc": "TRMB",

    # ZBRA - Zebra Technologies
    "zebra technologies": "ZBRA",
    "zebra": "ZBRA",

    # KEYS - Keysight Technologies
    "keysight": "KEYS",
    "keysight technologies": "KEYS",

    # TDY - Teledyne Technologies
    "teledyne": "TDY",
    "teledyne technologies": "TDY",

    # FTV - Fortive
    "fortive": "FTV",
    "fortive corp": "FTV",

    # CPAY - Corpay (already above in payments)

    # =========================================================================
    # ADDITIONAL COMPANIES (alphabetical fill)
    # =========================================================================

    # ACN - Accenture (already above in industrials)

    # AOS - A. O. Smith
    "a.o. smith": "AOS",
    "a. o. smith": "AOS",
    "ao smith": "AOS",

    # BAX - Baxter International
    "baxter": "BAX",
    "baxter international": "BAX",

    # BF.B - Brown-Forman
    "brown-forman": "BF.B",
    "brown forman": "BF.B",
    "jack daniels": "BF.B",
    "jack daniel's": "BF.B",

    # CAH - Cardinal Health
    "cardinal health": "CAH",
    "cardinal health inc": "CAH",

    # COR - Cencora
    "cencora": "COR",
    "amerisourcebergen": "COR",

    # DAY - Dayforce
    "dayforce": "DAY",
    "ceridian": "DAY",

    # DGX - Quest Diagnostics
    "quest diagnostics": "DGX",
    "quest": "DGX",

    # DVA - DaVita
    "davita": "DVA",
    "davita inc": "DVA",

    # EW - Edwards Lifesciences
    "edwards lifesciences": "EW",
    "edwards": "EW",

    # HOLX - Hologic
    "hologic": "HOLX",
    "hologic inc": "HOLX",

    # HSIC - Henry Schein
    "henry schein": "HSIC",
    "henry schein inc": "HSIC",

    # JCI - Johnson Controls
    "johnson controls": "JCI",
    "johnson controls international": "JCI",

    # LH - Labcorp
    "labcorp": "LH",
    "laboratory corp of america": "LH",
    "laboratory corporation of america": "LH",

    # PODD - Insulet Corporation
    "insulet": "PODD",
    "insulet corp": "PODD",
    "omnipod": "PODD",

    # RMD - ResMed
    "resmed": "RMD",
    "resmed inc": "RMD",

    # STE - Steris
    "steris": "STE",
    "steris plc": "STE",

    # VTRS - Viatris
    "viatris": "VTRS",
    "viatris inc": "VTRS",
    "mylan": "VTRS",

    # WST - West Pharmaceutical Services
    "west pharmaceutical": "WST",
    "west pharma": "WST",

    # WSM - Williams-Sonoma
    "williams-sonoma": "WSM",
    "williams sonoma": "WSM",
    "pottery barn": "WSM",
    "west elm": "WSM",

    # GPC - Genuine Parts Company
    "genuine parts": "GPC",
    "genuine parts company": "GPC",
    "napa auto parts": "GPC",

    # PAYC - Paycom
    "paycom": "PAYC",
    "paycom software": "PAYC",

    # PTC - PTC Inc.
    "ptc": "PTC",
    "ptc inc": "PTC",

    # TYL - Tyler Technologies
    "tyler technologies": "TYL",

    # SHW (already above)

    # WRB - W. R. Berkley Corporation
    "w.r. berkley": "WRB",
    "wr berkley": "WRB",
    "w. r. berkley": "WRB",

    # BXP - BXP, Inc.
    "bxp": "BXP",
    "boston properties": "BXP",

    # RVTY - Revvity
    "revvity": "RVTY",
    "perkinelmer": "RVTY",

    # NDSN - Nordson Corporation
    "nordson": "NDSN",
    "nordson corp": "NDSN",

    # HUBB - Hubbell Incorporated
    "hubbell": "HUBB",
    "hubbell inc": "HUBB",

    # JKHY - Jack Henry & Associates
    "jack henry": "JKHY",
    "jack henry & associates": "JKHY",

    # LII - Lennox International
    "lennox": "LII",
    "lennox international": "LII",

    # MAS - Masco
    "masco": "MAS",
    "masco corp": "MAS",

    # ROL - Rollins
    "rollins": "ROL",
    "rollins inc": "ROL",
    "orkin": "ROL",

    # SJM - J.M. Smucker
    "smucker": "SJM",
    "j.m. smucker": "SJM",
    "smuckers": "SJM",
    "the j.m. smucker company": "SJM",
    "jif": "SJM",

    # ALLE - Allegion
    "allegion": "ALLE",
    "allegion plc": "ALLE",

    # GEN - Gen Digital
    "gen digital": "GEN",
    "norton lifelock": "GEN",
    "nortonlifelock": "GEN",
    "symantec": "GEN",

    # IDEX Corporation
    "idex": "IEX",
    "idex corp": "IEX",

    # FRT - Federal Realty
    "federal realty": "FRT",
    "federal realty investment trust": "FRT",

    # KIM - Kimco Realty
    "kimco realty": "KIM",
    "kimco": "KIM",

    # MAA - Mid-America Apartment Communities
    "mid-america apartment": "MAA",
    "mid america apartment": "MAA",

    # O - Realty Income
    "realty income": "O",
    "realty income corp": "O",

    # REG - Regency Centers
    "regency centers": "REG",

    # UDR - UDR, Inc.
    "udr": "UDR",
    "udr inc": "UDR",

    # VTR - Ventas
    "ventas": "VTR",
    "ventas inc": "VTR",

    # WY - Weyerhaeuser
    "weyerhaeuser": "WY",
    "weyerhaeuser company": "WY",

    # HST - Host Hotels & Resorts
    "host hotels": "HST",
    "host hotels & resorts": "HST",

    # DOC - Healthpeak Properties
    "healthpeak": "DOC",
    "healthpeak properties": "DOC",

    # ESS - Essex Property Trust
    "essex property trust": "ESS",
    "essex property": "ESS",

    # CPT - Camden Property Trust
    "camden property trust": "CPT",
    "camden property": "CPT",

    # LNT - Alliant Energy
    "alliant energy": "LNT",

    # AEE - Ameren
    "ameren": "AEE",
    "ameren corp": "AEE",

    # AWK - American Water Works
    "american water works": "AWK",
    "american water": "AWK",

    # ATO - Atmos Energy
    "atmos energy": "ATO",
    "atmos": "ATO",

    # CMS - CMS Energy
    "cms energy": "CMS",

    # CNP - CenterPoint Energy
    "centerpoint energy": "CNP",
    "centerpoint": "CNP",

    # D - Dominion Energy
    "dominion energy": "D",
    "dominion": "D",

    # ES - Eversource Energy
    "eversource": "ES",
    "eversource energy": "ES",

    # EVRG - Evergy
    "evergy": "EVRG",
    "evergy inc": "EVRG",

    # FE - FirstEnergy
    "firstenergy": "FE",
    "firstenergy corp": "FE",

    # NI - NiSource
    "nisource": "NI",
    "nisource inc": "NI",

    # PEG - Public Service Enterprise Group
    "pseg": "PEG",
    "public service enterprise": "PEG",
    "ps enterprise group": "PEG",

    # PNW - Pinnacle West Capital
    "pinnacle west": "PNW",
    "pinnacle west capital": "PNW",

    # =========================================================================
    # TICKER-ONLY ALIASES (well-known tickers used in headlines with $)
    # =========================================================================

    "aapl": "AAPL",
    "amzn": "AMZN",
    "tsla": "TSLA",
    "nvda": "NVDA",
    "nflx": "NFLX",
    "jpm": "JPM",
    "bac": "BAC",
    "wfc": "WFC",
    "xom": "XOM",
    "cvx": "CVX",
    "jnj": "JNJ",
    "unh": "UNH",
    "pfe": "PFE",
    "abbv": "ABBV",
    "lly": "LLY",
    "mrk": "MRK",
    "pypl": "PYPL",
    "dis": "DIS",
    "cost": "COST",
    "crm": "CRM",
    "avgo": "AVGO",
    "qcom": "QCOM",
    "pltr": "PLTR",
    "coin": "COIN",
    "uber": "UBER",
    "abnb": "ABNB",
}


def get_ticker(alias: str) -> str | None:
    """
    Look up a ticker symbol from a company alias.

    Args:
        alias: Company name, abbreviation, or brand (case-insensitive)

    Returns:
        Ticker symbol string if found, None otherwise
    """
    return COMPANY_ALIASES.get(alias.lower().strip())


def get_all_aliases_for_ticker(ticker: str) -> list[str]:
    """
    Get all known aliases for a given ticker symbol.

    Args:
        ticker: The ticker symbol (e.g., "AAPL")

    Returns:
        List of alias strings that map to this ticker
    """
    ticker_upper = ticker.upper()
    return [alias for alias, t in COMPANY_ALIASES.items() if t == ticker_upper]


# Quick stats when run directly
if __name__ == "__main__":
    print(f"Total aliases: {len(COMPANY_ALIASES)}")
    tickers = set(COMPANY_ALIASES.values())
    print(f"Unique tickers covered: {len(tickers)}")

    # Show coverage for priority companies
    priority = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO",
        "ORCL", "CRM", "AMD", "INTC", "CSCO", "ADBE", "IBM", "NFLX",
        "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BRK.B", "V", "MA",
        "JNJ", "UNH", "PFE", "MRK", "ABBV", "LLY", "TMO", "ABT", "BMY",
        "WMT", "PG", "KO", "PEP", "COST", "MCD", "NKE", "SBUX", "TGT",
        "XOM", "CVX", "COP", "SLB", "EOG",
        "BA", "CAT", "HON", "UPS", "GE", "MMM", "RTX", "LMT", "DE",
        "DIS", "CMCSA", "T", "VZ", "TMUS",
        "PYPL", "XYZ", "UBER", "ABNB", "COIN", "PLTR",
    ]
    missing = [t for t in priority if t not in tickers]
    if missing:
        print(f"\nWARNING - Priority tickers missing: {missing}")
    else:
        print(f"\nAll {len(priority)} priority tickers covered!")

    # Show top tickers by alias count
    from collections import Counter
    ticker_counts = Counter(COMPANY_ALIASES.values())
    print("\nTop 20 tickers by alias count:")
    for ticker, count in ticker_counts.most_common(20):
        print(f"  {ticker}: {count} aliases")
