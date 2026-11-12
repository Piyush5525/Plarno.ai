"""Demo dataset. Coordinates are approximate real-world locations; prices, hours, AQI, noise and
safety values are SYNTHETIC/ESTIMATED and must be replaced by live providers (see docs/INTEGRATIONS.md).
`fee_inr=None` / `hours=None` means "unknown - verify with the official source" (never guessed)."""

CITIES = {  # name: (lat, lon, has_airport, has_rail, has_bus)
    "Delhi": (28.6139, 77.2090, 1, 1, 1), "Jaipur": (26.9124, 75.7873, 1, 1, 1),
    "Agra": (27.1767, 78.0081, 0, 1, 1), "Chandigarh": (30.7333, 76.7794, 1, 1, 1),
    "Manali": (32.2396, 77.1887, 0, 0, 1), "Kullu (Bhuntar)": (31.8767, 77.1544, 1, 0, 1),
    "Mumbai": (19.0760, 72.8777, 1, 1, 1), "Bengaluru": (12.9716, 77.5946, 1, 1, 1),
    "Kolkata": (22.5726, 88.3639, 1, 1, 1), "Lucknow": (26.8467, 80.9462, 1, 1, 1),
    "Varanasi": (25.3176, 82.9739, 1, 1, 1), "Goa": (15.2993, 74.1240, 1, 1, 1),
}

ATTRACTIONS = [
    # id, name, category, lat, lon, area, visit_min, fee_inr (None = verify), best_time, tags, accessibility
    ("red-fort", "Red Fort (Lal Qila)", "historical", 28.6562, 77.2410, "Old Delhi", 120, None, "Oct-Mar, morning", ["history", "mughal", "unesco"], "Partly wheelchair accessible; verify"),
    ("jama-masjid", "Jama Masjid", "religious", 28.6507, 77.2334, "Old Delhi", 60, None, "Morning; modest dress", ["history", "religious", "mughal"], "Many steps"),
    ("chandni-chowk", "Chandni Chowk", "market", 28.6506, 77.2303, "Old Delhi", 150, 0, "Late morning-evening", ["food", "shopping", "culture"], "Crowded, narrow lanes"),
    ("humayuns-tomb", "Humayun's Tomb", "historical", 28.5933, 77.2507, "Nizamuddin", 90, None, "Oct-Mar, late afternoon", ["history", "mughal", "unesco", "garden"], "Mostly level paths"),
    ("india-gate", "India Gate", "monument", 28.6129, 77.2295, "Central Delhi", 60, 0, "Evening", ["history", "monument", "park"], "Level, open lawns"),
    ("national-museum", "National Museum", "museum", 28.6117, 77.2191, "Central Delhi", 120, None, "Weekday", ["museum", "art", "history"], "Lifts available; verify"),
    ("purana-qila", "Purana Qila", "historical", 28.6096, 77.2437, "Central Delhi", 90, None, "Late afternoon", ["history", "fort", "boating"], "Uneven ground"),
    ("qutub-minar", "Qutub Minar Complex", "historical", 28.5245, 77.1855, "Mehrauli", 90, None, "Oct-Mar, morning", ["history", "unesco", "archaeology"], "Uneven ground"),
    ("lotus-temple", "Lotus Temple", "religious", 28.5535, 77.2588, "Kalkaji", 60, 0, "Late afternoon; closed Mondays (verify)", ["architecture", "peaceful", "religious"], "Ramps available"),
    ("lodhi-garden", "Lodhi Garden", "park", 28.5931, 77.2197, "Lodhi Colony", 75, 0, "Early morning", ["garden", "peaceful", "history"], "Paved paths"),
    ("hauz-khas", "Hauz Khas Village & Fort", "historical", 28.5494, 77.2001, "Hauz Khas", 120, None, "Afternoon-evening", ["history", "cafes", "nightlife"], "Uneven paths"),
    ("akshardham", "Swaminarayan Akshardham", "religious", 28.6127, 77.2773, "Akshardham", 180, None, "Afternoon; no phones/cameras inside", ["architecture", "religious", "culture"], "Wheelchairs provided; verify"),
    ("dilli-haat", "Dilli Haat INA", "market", 28.5726, 77.2084, "INA", 90, None, "Afternoon-evening", ["shopping", "crafts", "food"], "Mostly level"),
    ("sunder-nursery", "Sunder Nursery", "park", 28.5931, 77.2437, "Nizamuddin", 90, None, "Morning/late afternoon", ["garden", "peaceful", "heritage"], "Paved paths"),
]

NEIGHBOURHOODS = [
    # id, name, lat, lon, industrial_km (geographic proxy), green(0-1), aqi_est, noise_db_est, traffic(0-1), safety_idx(0-1 est), transit(0-1), hospitals, police
    ("cp", "Connaught Place", 28.6315, 77.2167, 9.0, 0.45, 180, 72, 0.85, 0.72, 0.98, 4, 2),
    ("lodhi", "Lodhi Colony / Defence Colony", 28.5870, 77.2290, 8.0, 0.80, 150, 58, 0.50, 0.85, 0.65, 4, 2),
    ("hauzkhas", "Hauz Khas / Safdarjung", 28.5500, 77.2050, 8.5, 0.65, 155, 62, 0.60, 0.80, 0.70, 5, 3),
    ("chanakya", "Chanakyapuri", 28.5980, 77.1870, 10.0, 0.85, 140, 55, 0.35, 0.90, 0.45, 3, 3),
    ("karolbagh", "Karol Bagh", 28.6510, 77.1900, 5.5, 0.15, 190, 78, 0.90, 0.60, 0.85, 3, 2),
    ("paharganj", "Paharganj", 28.6430, 77.2130, 6.5, 0.10, 195, 80, 0.90, 0.50, 0.90, 2, 2),
    ("olddelhi", "Old Delhi", 28.6560, 77.2300, 6.0, 0.10, 200, 82, 0.92, 0.55, 0.80, 3, 2),
    ("okhla", "Okhla", 28.5360, 77.2700, 0.8, 0.15, 210, 74, 0.70, 0.55, 0.60, 2, 1),
    ("mayurvihar", "Mayur Vihar", 28.6080, 77.2950, 3.5, 0.25, 185, 70, 0.75, 0.62, 0.65, 2, 1),
    ("dwarka", "Dwarka", 28.5921, 77.0460, 6.0, 0.35, 175, 66, 0.55, 0.68, 0.60, 3, 2),
]

HOTELS = [
    # id, name, nid, lat, lon, type, stars, rating, clean, interiors, food_q, base_price_inr(per night, SYNTHETIC)
    ("h-imperial-vista", "The Imperial Vista", "cp", 28.6310, 77.2190, "hotel", 5, 4.6, 4.8, 4.9, 4.7, 11500),
    ("h-lodhi-courtyard", "Lodhi Courtyard Suites", "lodhi", 28.5875, 77.2280, "hotel", 4, 4.5, 4.7, 4.6, 4.3, 5600),
    ("h-garden-haveli", "Garden Haveli Guest House", "lodhi", 28.5890, 77.2300, "guest_house", 3, 4.4, 4.5, 4.4, 4.2, 3400),
    ("h-hauz-retreat", "Hauz Khas Retreat", "hauzkhas", 28.5510, 77.2040, "hotel", 4, 4.3, 4.4, 4.5, 4.3, 4800),
    ("h-chanakya-heritage", "Chanakya Heritage Inn", "chanakya", 28.5985, 77.1880, "hotel", 4, 4.5, 4.6, 4.7, 4.4, 6200),
    ("h-karol-comfort", "Karol Bagh Comfort Stay", "karolbagh", 28.6500, 77.1910, "hotel", 3, 4.0, 4.0, 3.6, 3.8, 2400),
    ("h-pahar-hostel", "Backpackers' Nest Hostel", "paharganj", 28.6440, 77.2140, "hostel", 2, 4.1, 3.9, 3.5, 3.6, 900),
    ("h-old-haveli", "Old Delhi Haveli Stay", "olddelhi", 28.6550, 77.2290, "homestay", 3, 4.4, 4.2, 4.8, 4.5, 3900),
    ("h-okhla-business", "Okhla Business Inn", "okhla", 28.5370, 77.2690, "hotel", 3, 3.8, 3.9, 3.4, 3.5, 2000),
    ("h-cp-budget", "CP Central Budget Hotel", "cp", 28.6320, 77.2150, "hotel", 3, 4.0, 4.1, 3.7, 3.9, 3000),
    ("h-mayur-serviced", "Mayur Serviced Apartments", "mayurvihar", 28.6090, 77.2940, "serviced_apartment", 3, 4.1, 4.2, 3.9, 3.5, 2700),
    ("h-dwarka-resort", "Dwarka Greens Resort", "dwarka", 28.5930, 77.0480, "resort", 4, 4.2, 4.3, 4.3, 4.1, 4300),
]

RESTAURANTS = [
    # id, name, lat, lon, area, cuisine, price_for_two_inr (estimate), veg_friendly, vegan_friendly, rating, kind
    ("r-paranthe", "Paranthe-wali-gali style stalls", 28.6561, 77.2318, "Old Delhi", "North Indian street food", 300, True, False, 4.3, "street_food"),
    ("r-karims", "Karim's-style Mughlai kitchen", 28.6495, 77.2335, "Old Delhi", "Mughlai", 700, False, False, 4.2, "casual"),
    ("r-jalebi", "Old Famous Jalebi corner", 28.6563, 77.2300, "Old Delhi", "Sweets", 150, True, False, 4.4, "street_food"),
    ("r-cp-cafe", "Connaught Cafe Society", 28.6330, 77.2180, "Connaught Place", "Cafe / continental", 1200, True, True, 4.2, "cafe"),
    ("r-cp-fine", "Regal Dining Room", 28.6300, 77.2200, "Connaught Place", "North Indian fine dining", 3200, True, False, 4.5, "fine_dining"),
    ("r-hk-cafe", "Hauz Khas Lakeside Cafe", 28.5530, 77.1930, "Hauz Khas", "Cafe", 1400, True, True, 4.3, "cafe"),
    ("r-lodhi-thali", "Lodhi Thali House", 28.5900, 77.2270, "Lodhi Colony", "Vegetarian thali", 700, True, True, 4.4, "family"),
    ("r-nizam-kebab", "Nizamuddin Kebab Lane", 28.5890, 77.2440, "Nizamuddin", "Mughlai kebabs", 600, False, False, 4.3, "casual"),
    ("r-ina-south", "INA South Indian Canteen", 28.5740, 77.2100, "INA", "South Indian", 500, True, True, 4.1, "family"),
    ("r-mehrauli-cafe", "Mehrauli Garden Cafe", 28.5220, 77.1850, "Mehrauli", "Cafe", 1000, True, True, 4.0, "cafe"),
    ("r-kalkaji-veg", "Kalkaji Pure Veg", 28.5450, 77.2580, "Kalkaji", "North Indian vegetarian", 500, True, True, 4.0, "family"),
    ("r-india-gate-chaat", "India Gate Chaat Stalls", 28.6120, 77.2300, "Central Delhi", "Chaat", 250, True, False, 3.9, "street_food"),
]

# Raw supplier listings used for duplicate detection. `truth` is the canonical hotel id (evaluation only).
SUPPLIERS = {
    "StayHub": {"reliability": 0.92, "payment": "pay_now", "cancel": "free until 48h before check-in"},
    "RoomBazaar": {"reliability": 0.85, "payment": "pay_at_hotel", "cancel": "free until 24h before check-in"},
    "GlobeInventory": {"reliability": 0.78, "payment": "pay_now", "cancel": "non-refundable"},
}

SUPPLIER_LISTINGS = [
    # supplier, listing_id, name, lat, lon, room, beds, occupancy, meal, price_inr, truth
    ("StayHub", "SH-1", "The Imperial Vista", 28.6310, 77.2190, "Deluxe King Room", "1 King", 2, "Breakfast included", 11800, "h-imperial-vista"),
    ("RoomBazaar", "RB-77", "Imperial Vista Hotel, Connaught Place", 28.6312, 77.2188, "Deluxe Room King Bed", "1 King", 2, "Breakfast included", 11200, "h-imperial-vista"),
    ("GlobeInventory", "GI-9", "THE IMPERIAL VISTA NEW DELHI", 28.6309, 77.2191, "King Deluxe", "1 King", 2, "Room only", 10500, "h-imperial-vista"),
    ("StayHub", "SH-2", "Lodhi Courtyard Suites", 28.5875, 77.2280, "Superior Twin Room", "2 Twin", 2, "Breakfast included", 5800, "h-lodhi-courtyard"),
    ("RoomBazaar", "RB-12", "Lodhi Courtyard Suites & Spa", 28.5876, 77.2281, "Superior Room 2 Single Beds", "2 Twin", 2, "Breakfast included", 5500, "h-lodhi-courtyard"),
    ("GlobeInventory", "GI-14", "Lodhi Courtyard", 28.5874, 77.2279, "Twin Superior", "2 Twin", 2, "Room only", 5100, "h-lodhi-courtyard"),
    ("StayHub", "SH-3", "Garden Haveli Guest House", 28.5890, 77.2300, "Standard Double", "1 Double", 2, "Breakfast included", 3500, "h-garden-haveli"),
    ("RoomBazaar", "RB-30", "Garden Haveli Guesthouse Lodhi", 28.5891, 77.2299, "Standard Double Room", "1 Double", 2, "Breakfast included", 3300, "h-garden-haveli"),
    ("StayHub", "SH-4", "Hauz Khas Retreat", 28.5510, 77.2040, "Deluxe Double", "1 Double", 2, "Room only", 4900, "h-hauz-retreat"),
    ("GlobeInventory", "GI-3", "Hauz Khas Retreat Hotel", 28.5511, 77.2041, "Deluxe Double Room", "1 Double", 2, "Room only", 4600, "h-hauz-retreat"),
    # Hard negatives: similar names, different properties.
    ("RoomBazaar", "RB-90", "Imperial Vista Hostel Karol Bagh", 28.6505, 77.1905, "Dorm Bed", "1 Bunk", 1, "Room only", 700, "h-karol-hostel-x"),
    ("GlobeInventory", "GI-40", "Hauz Khas Retreat Annexe (Mumbai)", 19.1000, 72.8300, "Deluxe Double", "1 Double", 2, "Room only", 5200, "h-hk-mumbai-x"),
    ("StayHub", "SH-5", "Chanakya Heritage Inn", 28.5985, 77.1880, "Heritage Room", "1 King", 2, "Breakfast included", 6400, "h-chanakya-heritage"),
    ("RoomBazaar", "RB-51", "Chanakya Heritage Inn Delhi", 28.5984, 77.1881, "Heritage King Room", "1 King", 2, "Breakfast included", 6100, "h-chanakya-heritage"),
]

SAFETY_ADVISORY = {
    "Delhi": {
        "general": "Official government travel advisories should be consulted before travel (e.g. India's MEA / your own government's advisory service). No live advisory feed is connected in this prototype.",
        "tips": ["Prefer app-based or prepaid cabs at night.", "Keep valuables secure in crowded markets.", "Carry a photo ID.",
                 "Dress modestly at religious sites."],
        "emergency": {"National emergency number": "112", "Police": "100", "Ambulance": "102", "Women helpline": "1091",
                      "Tourist helpline": "1363"},
    }
}
