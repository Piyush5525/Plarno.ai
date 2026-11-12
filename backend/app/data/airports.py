"""City -> primary IATA airport code (for flight search). Hand-maintained; extend freely. Keys are lower-case."""
_RAW = """Delhi DEL;Mumbai BOM;Bengaluru BLR;Kolkata CCU;Chennai MAA;Hyderabad HYD;Pune PNQ;Ahmedabad AMD;Jaipur JAI;Goa GOI;Kochi COK;Thiruvananthapuram TRV;
Lucknow LKO;Varanasi VNS;Chandigarh IXC;Amritsar ATQ;Srinagar SXR;Leh IXL;Udaipur UDR;Jodhpur JDH;Patna PAT;Bhubaneswar BBI;Guwahati GAU;Indore IDR;Nagpur NAG;
Dehradun DED;Kullu KUU;Mangaluru IXE;Coimbatore CJB;Madurai IXM;Tiruchirappalli TRZ;Mysuru MYQ;Hubballi HBX;Belagavi IXG;Visakhapatnam VTZ;Vijayawada VGA;Tirupati TIR;Rajahmundry RJA;Tuticorin TCR;Salem SXV;Puducherry PNY;Kozhikode CCJ;Kannur CNN;Raipur RPR;Ranchi IXR;Bhopal BHO;Jabalpur JLR;Gwalior GWL;Surat STV;Vadodara BDQ;Rajkot RAJ;Aurangabad IXU;Nashik ISK;Kolhapur KLH;Shirdi SAG;Prayagraj IXD;Gaya GAY;Siliguri IXB;Jammu IXJ;Imphal IMF;Agartala IXA;Dibrugarh DIB;Dimapur DMU;Port Blair IXZ;London LHR;Paris CDG;New York JFK;Los Angeles LAX;San Francisco SFO;Chicago ORD;Miami MIA;Washington IAD;Boston BOS;Seattle SEA;Las Vegas LAS;
Toronto YYZ;Vancouver YVR;Mexico City MEX;Cancun CUN;Sao Paulo GRU;Rio de Janeiro GIG;Buenos Aires EZE;Lima LIM;Bogota BOG;Santiago SCL;Dubai DXB;Abu Dhabi AUH;Doha DOH;
Istanbul IST;Cairo CAI;Marrakech RAK;Cape Town CPT;Johannesburg JNB;Nairobi NBO;Addis Ababa ADD;Lagos LOS;Tel Aviv TLV;Amman AMM;Riyadh RUH;Singapore SIN;Kuala Lumpur KUL;
Bangkok BKK;Phuket HKT;Bali DPS;Denpasar DPS;Jakarta CGK;Hanoi HAN;Ho Chi Minh City SGN;Manila MNL;Hong Kong HKG;Shanghai PVG;Beijing PEK;Tokyo HND;Osaka KIX;Kyoto KIX;
Seoul ICN;Taipei TPE;Kathmandu KTM;Colombo CMB;Dhaka DAC;Male MLE;Karachi KHI;Sydney SYD;Melbourne MEL;Auckland AKL;Rome FCO;Milan MXP;Venice VCE;Florence FLR;
Barcelona BCN;Madrid MAD;Lisbon LIS;Amsterdam AMS;Brussels BRU;Berlin BER;Munich MUC;Frankfurt FRA;Vienna VIE;Prague PRG;Budapest BUD;Warsaw WAW;Zurich ZRH;Geneva GVA;
Athens ATH;Copenhagen CPH;Stockholm ARN;Oslo OSL;Helsinki HEL;Reykjavik KEF;Dublin DUB;Edinburgh EDI;Moscow SVO;Santorini JTR"""
ALIASES = {"mangalore": "mangaluru", "mysore": "mysuru", "trichy": "tiruchirappalli", "tiruchirapalli": "tiruchirappalli", "vizag": "visakhapatnam", "calicut": "kozhikode", "belgaum": "belagavi", "hubli": "hubballi", "pondicherry": "puducherry", "allahabad": "prayagraj", "bagdogra": "siliguri", "cochin": "kochi", "baroda": "vadodara", "tirunelveli": "tuticorin", "kolhapur city": "kolhapur", "new delhi": "delhi", "bangalore": "bengaluru", "bombay": "mumbai", "calcutta": "kolkata", "madras": "chennai", "trivandrum": "thiruvananthapuram",
           "saigon": "ho chi minh city", "nyc": "new york", "new york city": "new york", "la": "los angeles", "kl": "kuala lumpur", "panaji": "goa", "são paulo": "sao paulo",
           "praha": "prague", "wien": "vienna", "münchen": "munich", "köln": "frankfurt", "bhuntar": "kullu", "kullu (bhuntar)": "kullu", "zürich": "zurich", "genève": "geneva",
           "københavn": "copenhagen", "roma": "rome", "firenze": "florence", "venezia": "venice", "milano": "milan", "lisboa": "lisbon", "moskva": "moscow", "bogotá": "bogota",
           "malé": "male", "peking": "beijing", "krung thep": "bangkok", "ciudad de méxico": "mexico city", "reykjavík": "reykjavik", "edinburgh": "edinburgh"}
AIRPORTS = {k.strip().lower(): v.strip() for k, v in (item.rsplit(" ", 1) for item in _RAW.replace("\n", "").split(";") if item.strip())}


def iata(city: str | None) -> str | None:
    if not city:
        return None
    c = city.strip().lower()
    return AIRPORTS.get(ALIASES.get(c, c))


import json as _json
import math as _math
from pathlib import Path as _Path

_GEO = _json.loads((_Path(__file__).with_name("airports_geo.json")).read_text(encoding="utf-8"))


def _km(a, b):
    la1, lo1, la2, lo2 = map(_math.radians, (a[0], a[1], b[0], b[1]))
    d = _math.sin((la2 - la1) / 2) ** 2 + _math.cos(la1) * _math.cos(la2) * _math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0088 * _math.asin(_math.sqrt(d))


def nearest_airport(lat: float, lon: float, max_km: float = 400) -> dict | None:
    """Closest airport city in the table: {city, iata, km, lat, lon}. None if nothing within max_km."""
    best = None
    for city, g in _GEO.items():
        d = _km((lat, lon), (g["lat"], g["lon"]))
        if best is None or d < best["km"]:
            best = {"city": city.title(), "iata": g["iata"], "km": round(d, 1), "lat": g["lat"], "lon": g["lon"]}
    return best if best and best["km"] <= max_km else None
