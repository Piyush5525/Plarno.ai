"""Major Indian railway stations (code, station name, city, lat, lon) used to build honest door-to-door train options:
cab or bus to the nearest MAJOR station, a train between two real stations, then onward to the destination.
Only stations with frequent long-distance services are listed, because a tiny halt nearby is rarely where your train stops.
Coordinates are station/city-level approximations (good to a few km): fine for choosing the nearest station and estimating distance,
not for navigation. Hand-maintained; extend freely."""
import math

_RAW = """NDLS|New Delhi|Delhi|28.6429|77.2191
CSMT|Mumbai CSMT|Mumbai|18.9398|72.8355
HWH|Howrah Junction|Kolkata|22.5839|88.3425
MAS|Chennai Central|Chennai|13.0827|80.2757
SBC|KSR Bengaluru City|Bengaluru|12.9781|77.5697
SC|Secunderabad Junction|Hyderabad|17.4337|78.5016
ADI|Ahmedabad Junction|Ahmedabad|23.0258|72.5970
PUNE|Pune Junction|Pune|18.5286|73.8743
JP|Jaipur Junction|Jaipur|26.9196|75.7878
LKO|Lucknow Charbagh|Lucknow|26.8315|80.9216
CNB|Kanpur Central|Kanpur|26.4537|80.3513
PNBE|Patna Junction|Patna|25.6030|85.1376
BBS|Bhubaneswar|Bhubaneswar|20.2656|85.8433
GHY|Guwahati|Guwahati|26.1820|91.7513
CDG|Chandigarh Junction|Chandigarh|30.7030|76.8218
ASR|Amritsar Junction|Amritsar|31.6331|74.8656
JAT|Jammu Tawi|Jammu|32.7061|74.8802
SVDK|Shri Mata Vaishno Devi Katra|Katra|32.9830|74.9340
UMB|Ambala Cantt|Ambala|30.3384|76.8242
LDH|Ludhiana Junction|Ludhiana|30.9120|75.8483
JUC|Jalandhar City|Jalandhar|31.3310|75.5900
PTK|Pathankot Junction|Pathankot|32.2650|75.6440
UHL|Una Himachal|Una|31.4690|76.2700
KLK|Kalka|Kalka|30.8390|76.9340
DDN|Dehradun|Dehradun|30.3140|78.0330
HW|Haridwar Junction|Haridwar|29.9470|78.1610
RK|Roorkee|Roorkee|29.8520|77.8880
KGM|Kathgodam|Kathgodam|29.2680|79.5450
BE|Bareilly Junction|Bareilly|28.3410|79.4190
MB|Moradabad Junction|Moradabad|28.8320|78.7650
MTC|Meerut City|Meerut|28.9780|77.6710
ALJN|Aligarh Junction|Aligarh|27.8900|78.0740
AGC|Agra Cantt|Agra|27.1580|77.9900
MTJ|Mathura Junction|Mathura|27.4800|77.6730
GWL|Gwalior Junction|Gwalior|26.2160|78.1820
VGLJ|Virangana Lakshmibai Jhansi|Jhansi|25.4440|78.5540
BPL|Bhopal Junction|Bhopal|23.2660|77.4130
INDB|Indore Junction|Indore|22.7170|75.8680
UJN|Ujjain Junction|Ujjain|23.1830|75.7790
JBP|Jabalpur Junction|Jabalpur|23.1650|79.9510
NGP|Nagpur Junction|Nagpur|21.1520|79.0890
R|Raipur Junction|Raipur|21.2560|81.6300
BSP|Bilaspur Junction|Bilaspur|22.0700|82.1500
RNC|Ranchi Junction|Ranchi|23.3490|85.3340
TATA|Tatanagar Junction|Jamshedpur|22.7700|86.2030
DHN|Dhanbad Junction|Dhanbad|23.7920|86.4300
ROU|Rourkela Junction|Rourkela|22.2270|84.8640
KGP|Kharagpur Junction|Kharagpur|22.3400|87.3250
ASN|Asansol Junction|Asansol|23.6910|86.9750
GAYA|Gaya Junction|Gaya|24.8030|84.9990
BGP|Bhagalpur Junction|Bhagalpur|25.2420|87.0000
MFP|Muzaffarpur Junction|Muzaffarpur|26.1220|85.3780
BSB|Varanasi Junction|Varanasi|25.3270|82.9860
PRYJ|Prayagraj Junction|Prayagraj|25.4460|81.8290
GKP|Gorakhpur Junction|Gorakhpur|26.7600|83.3810
KOTA|Kota Junction|Kota|25.2230|75.8800
AII|Ajmer Junction|Ajmer|26.4560|74.6370
JU|Jodhpur Junction|Jodhpur|26.2850|73.0230
UDZ|Udaipur City|Udaipur|24.5720|73.6970
BKN|Bikaner Junction|Bikaner|28.0140|73.3190
JSM|Jaisalmer|Jaisalmer|26.9200|70.9050
ABR|Abu Road|Abu Road|24.4800|72.7800
SWM|Sawai Madhopur Junction|Sawai Madhopur|26.0180|76.3560
BRC|Vadodara Junction|Vadodara|22.3100|73.1810
ANND|Anand Junction|Anand|22.5600|72.9660
ST|Surat|Surat|21.2050|72.8410
RJT|Rajkot Junction|Rajkot|22.3130|70.8020
NK|Nashik Road|Nashik|19.9480|73.8420
AWB|Aurangabad|Aurangabad|19.8600|75.3100
KOP|Kolhapur|Kolhapur|16.7030|74.2380
SUR|Solapur Junction|Solapur|17.6640|75.8930
MAO|Madgaon Junction|Goa|15.2670|73.9710
UBL|Hubballi Junction|Hubballi|15.3500|75.1490
BGM|Belagavi|Belagavi|15.8500|74.5080
MAJN|Mangaluru Junction|Mangaluru|12.8660|74.8790
UD|Udupi|Udupi|13.3340|74.7590
MYS|Mysuru Junction|Mysuru|12.3160|76.6460
ERS|Ernakulam Junction|Kochi|9.9690|76.2910
TVC|Thiruvananthapuram Central|Thiruvananthapuram|8.4870|76.9520
CLT|Kozhikode|Kozhikode|11.2460|75.7810
CAN|Kannur|Kannur|11.8690|75.3650
TCR|Thrissur|Thrissur|10.5150|76.2080
CBE|Coimbatore Junction|Coimbatore|10.9960|76.9670
MDU|Madurai Junction|Madurai|9.9190|78.1100
TPJ|Tiruchirappalli Junction|Tiruchirappalli|10.7950|78.6850
SA|Salem Junction|Salem|11.6710|78.1130
KPD|Katpadi Junction|Vellore|12.9720|79.1380
PDY|Puducherry|Puducherry|11.9250|79.8280
TPTY|Tirupati|Tirupati|13.6280|79.4190
BZA|Vijayawada Junction|Vijayawada|16.5180|80.6200
VSKP|Visakhapatnam Junction|Visakhapatnam|17.7220|83.2890
RJY|Rajahmundry|Rajahmundry|17.0000|81.7900
WL|Warangal|Warangal|17.9720|79.6040
CAPE|Kanyakumari|Kanyakumari|8.0860|77.5480
PURI|Puri|Puri|19.8090|85.8380
NJP|New Jalpaiguri|Siliguri|26.6830|88.4430
DBRG|Dibrugarh|Dibrugarh|27.4700|94.9120
DMV|Dimapur|Dimapur|25.9050|93.7280
AGTL|Agartala|Agartala|23.7920|91.2780"""

STATIONS = [{"code": c, "name": n, "city": city, "lat": float(la), "lon": float(lo)} for c, n, city, la, lo in (row.split("|") for row in _RAW.splitlines())]


def _km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(d))


def nearest_station(lat: float, lon: float, max_km: float = 150) -> dict | None:
    """Closest major station: {code, name, city, lat, lon, km} (straight-line km), or None if none within max_km."""
    best = min(STATIONS, key=lambda s: _km((lat, lon), (s["lat"], s["lon"])))
    km = _km((lat, lon), (best["lat"], best["lon"]))
    return {**best, "km": round(km, 1)} if km <= max_km else None
