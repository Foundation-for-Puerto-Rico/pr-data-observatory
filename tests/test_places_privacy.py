"""Tests for places_privacy.py: private homes, housing, listings named by an address and care services are counted but never drawn, and no
place carries a contact detail (owner rule of 2026-10-18; docs/places-privacy.md).

  python -m unittest tests.test_places_privacy -v

The rule tests use invented names (no withheld listing's name is written in this file or anywhere in the repository; HiddenNames checks that).
The published-file tests fail if a drawn place matches a pattern without a review in places_review.json, if a withheld place keeps its name, id,
point or update date, or if any contact field comes back.
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import access  # noqa: E402
import places_privacy as pp  # noqa: E402
from test_access import AS_OF, operators, place, stop  # noqa: E402

DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache" / "overture_pr_places.geojson"
RV = pp.load_review()


def why(name, category):
    hits = pp.matches(name, category, RV)
    return hits[0] if hits else None


class Rule(unittest.TestCase):
    """What a name means in each kind of Overture category (invented names)."""

    def test_a_home_word_withholds_only_where_homes_are_filed(self):
        self.assertEqual(why("Casa Ejemplo Rivera", "historic_site"), "residence")
        self.assertEqual(why("Hacienda Ejemplo", "historic_site"), "residence")
        self.assertEqual(why("Residencia Ejemplo", "monument"), "residence")
        self.assertIsNone(why("Casa Ejemplo", "restaurant"))            # a restaurant called Casa ... is a business
        self.assertIsNone(why("Casa Ejemplo", "guest_house"))
        self.assertIsNone(why("Casa Ejemplo", "museum"))
        self.assertEqual(why("Casa Ejemplo", "holiday_rental_home"), "holiday_rental")   # a holiday rental (decision 48), not a residence

    def test_a_home_word_beside_a_business_or_a_public_venue_names_the_business(self):
        self.assertIsNone(why("Villa Ejemplo Guest House", "lodging"))
        self.assertEqual(why("Casa Ejemplo Vacation Rentals", "lodging"), "holiday_rental")   # a business, but a holiday rental (decision 48), not a residence
        self.assertIsNone(why("Parque de Pelota Villa Ejemplo", "park"))
        self.assertIsNone(why("Playa Villa Ejemplo", "beach"))
        self.assertEqual(why("Villa Ejemplo Playa Santa", "beach"), "residence")   # a house at a beach: the beach is not named first

    def test_housing_words(self):
        self.assertEqual(why("Urb. Ejemplo", "lodging"), "residential")
        self.assertEqual(why("Urb. Ejemplo", "hotel"), "residential")         # a housing word first withholds in any category
        self.assertEqual(why("Residencial Ejemplo", "historic_site"), "residential")
        self.assertEqual(why("Condominio Ejemplo", "historic_site"), "residential")
        self.assertEqual(why("Ejemplo Apartments", "historic_site"), "residential")
        self.assertEqual(why("Ejemplo Apartments", "hotel"), "holiday_rental")   # units rented out: a real aparthotel is drawn by review
        self.assertIsNone(why("Ejemplo Apartments", "restaurant"))
        self.assertIsNone(why("Iglesia Ejemplo Parcelas Nuevas", "christian_place_of_worship"))   # the venue is named first
        self.assertEqual(why("Mobile Ejemplo", "mobile_home_park"), "residential")

    def test_a_lodging_listing_must_name_an_accommodation(self):
        self.assertEqual(why("Barrio Ejemplo, Pueblo", "lodging"), "residential")
        self.assertIsNone(why("Hotel Ejemplo", "lodging"))
        self.assertIsNone(why("Ejemplo Guest House", "lodging"))
        self.assertEqual(why("Ejemplo Short Term Rental", "lodging"), "holiday_rental")   # names an accommodation, but a holiday rental (decision 48)

    def test_an_address_or_a_unit_number(self):
        self.assertEqual(why("Urb. Ejemplo Calle Luna K7 Pueblo 00949", "historic_site"), "address")
        self.assertEqual(why("12 Calle Ejemplo", "bar"), "address")
        self.assertEqual(why("Ejemplo Beach Apt. 208", "holiday_rental_home"), "address")
        self.assertEqual(why("Ejemplo 1571", "historic_site"), "address")
        self.assertIsNone(why("Pizza Ejemplo #2", "pizza_restaurant"))          # a branch number
        self.assertIsNone(why("Calle 25 de Enero", "historic_site"))            # a street, not a house
        self.assertIsNone(why("Centro Cultural Ejemplo 1962", "historic_site"))  # a year
        self.assertIsNone(why("Carretera 149 Ejemplo", "geographic_entities"))  # a road number

    def test_a_home_word_and_a_unit_or_house_number_in_any_category(self):
        for name, cat in (("Casa Ejemplo 28", "hotel"), ("Casa Ejemplo 28", "restaurant"), ("Casa Ejemplo 28", "museum"), ("Ejemplo Cluster 2 - 39B", "hotel"),
                          ("Rio Ejemplo Cluster 2 - 39B Villa Ficticia", "hotel"), ("Villa Ejemplo 53 - Ficticia", "historic_site"), ("Villa 12", "campground"),
                          ("Casita 12", "bar"), ("Ejemplo Home 7B", "art_gallery"), ("Bungalow 7 Ejemplo", "hotel"), ("Apartamento Ejemplo #3", "lodging")):
            self.assertEqual(why(name, cat), "address", (name, cat))
        for name, cat in (("Casa Ejemplo 2", "restaurant"),            # one digit outside the home and rental categories: a branch number
                          ("La Casita del Sabor 12", "restaurant"),     # a food business named
                          ("Casa Ejemplo 1898", "museum"),              # a year
                          ("Iglesia Casa de Oración 24", "christian_place_of_worship"), ("Parque Villa Ejemplo 2", "park"),
                          ("Ejemplo Guest House 28", "hotel"), ("Studio 54", "bar")):
            self.assertIsNone(why(name, cat), (name, cat))

    def test_a_holiday_rental_is_counted_not_drawn(self):
        """Decision 48 (2026-10-18): a holiday rental is usually someone's home; hotels, guest houses, inns and B&Bs stay drawn."""
        for cat in ("holiday_rental_home", "cabin", "cottage", "service_apartment"):   # by category, whatever the name
            self.assertEqual(why("Ejemplo", cat), "holiday_rental", cat)
            self.assertEqual(why("Ejemplo Guest House", cat), "holiday_rental", cat)   # a guest house filed as a rental is drawn only by review
        for name, cat in (("Ejemplo Beach House", "hotel"), ("Ejemplo Vacation Rental", "resort"), ("Ejemplo Airbnb", "bed_and_breakfast"),
                          ("Ejemplo Short Term Rental Apartment", "lodging"), ("Ejemplo Tiny House", "lodging"), ("Ejemplo Rentals", "lodging"),
                          ("Ejemplo Stays", "hotel"), ("Ejemplo Beach House", "beach"), ("Ejemplo Vacation Apartment", "historic_site"),
                          ("Ejemploairbnb", "hotel"), ("Apartamento Vacacional Ejemplo", "hotel"), ("Estudio para Alquiler", "historic_site")):
            self.assertEqual(why(name, cat), "holiday_rental", (name, cat))
        for name, cat in (("Hotel Ejemplo", "hotel"), ("Ejemplo Guest House", "guest_house"), ("Ejemplo Inn", "inn"), ("Ejemplo B&B", "bed_and_breakfast"),
                          ("Ejemplo Beach House - Guest House", "hotel"), ("Posada Ejemplo Vacation Apartments", "hotel"),
                          ("Ejemplo Beach House", "restaurant"), ("Ejemplo Kayak Rental", "visitor_center"), ("Ejemplo Boat Rentals", "historic_site"),
                          ("Ejemplo Vacation Club", "resort")):
            self.assertIsNone(why(name, cat), (name, cat))
        self.assertEqual(why("Ejemplo Beach Apt. 208", "holiday_rental_home"), "address")   # an address is recorded first

    def test_a_unit_or_a_house_rented_out_from_a_hotel_category(self):
        """Holiday rentals filed as hotels, B&Bs, hostels or campgrounds, named by the unit or house they rent (review of 2026-10-18)."""
        for cat in ("hotel", "bed_and_breakfast", "hostel", "campground", "resort", "lodge", "motel"):
            for name in ("Ejemplo Beach Apartment", "Apartamento Ejemplo", "Apto Ejemplo", "Ejemplo Ocean View Condo", "Ejemplo Studio", "Estudio Ejemplo",
                         "Ejemplo Loft", "Penthouse Ejemplo", "Casita Ejemplo", "La Casita Ejemplo de Ficticia", "Ejemplo Bungalow", "Cabaña Ejemplo",
                         "Ejemplo Apartments", "Apartamentos Ejemplo", "Ejemplo Studios", "Ejemplo Condos", "Casa Ejemplo", "Villa Ejemplo", "Villa de Doe",
                         "Casa Los Doe", "Casa Doe's", "Villa Ejemplo PR", "Casa Ejemplo Puerto Rico"):
                self.assertEqual(why(name, cat), "holiday_rental", (name, cat))
        for name in ("Casa Ejemplo Guest House", "Villa Ejemplo Hotel", "Ejemplo Apartments Hotel", "Casita Ejemplo Inn", "Casa Ejemplo B&B", "Hostel Casa Ejemplo",
                     "Posada Villa Ejemplo", "Parador Casa Ejemplo", "Ejemplo Beach Resort Villa", "Casa Ejemplo Grande del Mar", "Hotel Ejemplo"):
            self.assertIsNone(why(name, "hotel"), name)   # a lodging business named, or more than one word after Casa
        for cat in ("guest_house", "inn", "restaurant", "bar", "museum", "cafe"):   # outside unit_names a unit or house word is not a rental
            for name in ("Casa Ejemplo", "Ejemplo Studio", "Villa Ejemplo", "Casita Ejemplo", "Ejemplo Apartments"):
                self.assertNotEqual(why(name, cat), "holiday_rental", (name, cat))
        self.assertEqual(why("Jane Doe's Beach House", "hotel"), "holiday_rental")

    def test_a_house_a_villa_or_a_condominium_rented_out_from_a_hotel_category(self):
        """Re-review of PR #60 (2026-10-18): '... House', '... Home', a final 'Villa', 'Casa/Villa' and one word followed by a town, and 'Condominio ...'."""
        self.assertIn("rincon", pp.place_names())
        for cat in ("hotel", "bed_and_breakfast", "hostel", "lodge", "resort", "beach_resort"):
            for name in ("Jane Doe's Little House", "Big Ejemplo House", "The Ejemplo Vibes house", "Ejemplo House - Yabucoa, Puerto Rico", "Ejemplo Beach Home",
                         "Ejemplo Ficticia Villa", "Ejemplo View Villa", "Ejemplo Horizon Villa PR", "Our Ejemplo La Villa",
                         "Casa Ejemplo Rincón", "Casa Ejemplo Moca", "Casa Ejemplo Rincon", "Casa Doe, Culebra PR", "Villa Ejemplo, Luquillo, Puerto Rico",
                         "Casa de Ejemplo Hatillo", "Condominio Ejemplo, Rio Piedras", "Condominio Villa Ejemplo", "Ejemplo Del Mar Condominium"):
                self.assertEqual(why(name, cat), "holiday_rental", (name, cat))
        for name in ("Ejemplo Guest House", "Ejemplo House Inn", "Hotel Ejemplo House", "Villa Ejemplo Resort", "Ejemplo Villas Hotel", "Casa Ejemplo Ficticia Doe",
                     "Casa Ejemplo Grande del Mar", "Ejemplo Villas", "Home2 Ejemplo Suites", "Ejemplo Housekeeping"):
            self.assertIsNone(why(name, "hotel"), name)
        for cat in ("restaurant", "bar", "museum", "guest_house", "inn"):
            for name in ("Ejemplo House", "Casa Ejemplo Rincón", "Condominio Ejemplo", "Ejemplo View Villa"):
                self.assertNotEqual(why(name, cat), "holiday_rental", (name, cat))
        for cat in ("hotel", "lodging", "bed_and_breakfast", "campground"):   # cabins, chalets and cottages
            for name in ("Ejemplo Cabin", "Cabin in the Ejemplo", "Chalet Ejemplo", "Chalet del Ejemplo", "Ejemplo Cottage", "Tiny Ejemplo Cabin"):
                self.assertIn(why(name, cat), ("holiday_rental", "residential") if cat == "lodging" else ("holiday_rental",), (name, cat))   # a lodging listing that names no accommodation is housing first
        self.assertIsNone(why("Ejemplo Cabin Hotel", "hotel"))
        self.assertIsNone(why("Ejemplo Cottage Inn", "hotel"))
        for cat in ("restaurant", "bar", "museum", "guest_house", "inn"):
            self.assertIsNone(why("Ejemplo Cabin", cat), cat)
        # "Casa/Villa" and one word followed by a neighborhood, sector or urbanización (gazetteer kind 'neighborhood')
        self.assertIn("isla verde", pp.place_names())
        for name in ("Casa Ejemplo Isla Verde", "Casa Ejemplo Castañer PR", "Villa Ejemplo, Isla Verde"):
            self.assertEqual(why(name, "hotel"), "holiday_rental", name)
            for cat in ("restaurant", "bar", "museum", "guest_house", "inn"):
                self.assertNotEqual(why(name, cat), "holiday_rental", (name, cat))
        sourced = [v for v in RV["public"].values() if v.get("source")]
        self.assertGreaterEqual(len(sourced), 14, "each lodging business drawn by the 2026-10-18 reviews names the source checked")
        reviewed = [k for k, v in RV["public"].items() if "rooms" in v["reason"] or "aparthotel" in v["reason"]]
        self.assertGreaterEqual(len(reviewed), 9, "the guest houses, hostels and aparthotels drawn by the 2026-10-18 review")
        drawn = [k for k, v in RV["public"].items() if "decision 48" in v["reason"]]
        self.assertTrue(drawn and all(re.search(r"guest ?house|hotel", v["name"], re.I) for k, v in RV["public"].items() if k in drawn),
                        "a holiday-rental listing is drawn only when its name says guest house or hotel")

    def test_a_care_shelter_or_treatment_service_in_any_category(self):
        for name in ("Hogar de Envejecientes Ejemplo", "Égida Ejemplo", "Centro de Rehabilitación Ejemplo", "Hospicio Ejemplo", "Casa Protegida Ejemplo",
                     "Ejemplo Senior Living", "Hogar CREA Ejemplo"):
            for cat in ("lodging", "hotel", "christian_place_of_worship", "historic_site"):
                self.assertEqual(why(name, cat), "sensitive", (name, cat))

    def test_care_foster_and_recovery_homes(self):
        """Final review of PR #60 (2026-10-18): a licensed care home is often filed as "Hogar <name>, Inc." under a hotel or B&B category."""
        for cat in ("hotel", "bed_and_breakfast", "lodging", "hostel", "campground", "guest_house", "inn", "resort"):
            for name in ("Hogar Ejemplo Inc.", "Hogar Ejemplo", "Hogar Casa Ejemplo", "Institución Hogar Ejemplo"):
                self.assertEqual(why(name, cat), "sensitive", (name, cat))
        for cat in ("airport", "religious_organization", "christian_place_of_worship", "religious_school", "restaurant", "historic_site"):
            for name in ("Institución Hogar Ejemplo", "Hogar de Restauración Ejemplo", "Casa Hogar Ejemplo", "Colegio Hogar Ejemplo", "Hogar de Crianza Ejemplo",
                         "Hogar Sustituto Ejemplo", "Hogar Geriátrico Ejemplo", "Ejemplo Group Home", "Ejemplo Foster Home", "Ejemplo Halfway House",
                         "Ejemplo Sober Living", "Ejemplo Safe House", "Ejemplo Orphanage", "Centro de Tratamiento Ejemplo", "Hogar CREA Ejemplo"):
                self.assertEqual(why(name, cat), "sensitive", (name, cat))
        for name, cat in (("Hogar Ejemplo", "restaurant"), ("Hogareño Ejemplo", "hotel"), ("Plaza Ejemplo de la Convalecencia", "park"),
                          ("Iglesia Casa de Restauración Ejemplo", "christian_place_of_worship"), ("Ejemplo Hogar y Jardín", "arts_and_entertainment"),
                          ("Casa Ejemplo, Hogar de la Cultura", "history_museum")):
            self.assertIsNone(why(name, cat), (name, cat))

    def test_shelters_reviewed_by_id(self):
        """Last review of PR #60 (2026-10-18, "when in doubt, hide"): shelters and care homes no pattern names, withheld by Overture id with a note and no name;
        the old poorhouse is counted, not drawn, in the National Register layer too."""
        for oid in ("c0a6b574-70c8-4445-8c28-ecbe35284bda", "ed2e5264-afdf-428f-9537-0c21069f5863", "c0f4977d-b163-41a8-8c5a-e3d1d385d26d",
                    "35b5f2e0-b354-408e-a1e4-16aa3736259e", "cc738838-a352-4168-9462-f42f98d9c34a"):
            self.assertEqual(RV["withheld"].get(oid), "sensitive", oid)
            self.assertTrue(RV["withheld_notes"].get(oid), oid)
        nrhp = json.loads((ROOT / "nrhp_review.json").read_text(encoding="utf-8"))
        self.assertIn("85003087", nrhp["residence"])

    def test_services_run_from_a_home_under_a_name(self):
        self.assertEqual(why("Ejemplo Tarot", "psychic_advising"), "residence")

    def test_the_reviewed_list_wins(self):
        oid = next(iter(RV["public"]))
        self.assertIsNone(pp.reason({"oid": oid, "name": "Casa Ejemplo", "overture_category": "historic_site"}, RV))
        oid = next(iter(RV["withheld"]))
        self.assertEqual(pp.reason({"oid": oid, "name": "Bar Ejemplo", "overture_category": "bar"}, RV), RV["withheld"][oid])


class NotTourism(unittest.TestCase):
    """Decision 47 (2026-10-18): homes, housing and care services are not tourism, so they are not counted; holiday rentals are (invented names)."""

    def place(self, name, category):
        p = {"oid": "x-" + name, "name": name, "overture_category": category}
        p["withheld"] = pp.reason(p, RV)
        return p

    def test_homes_housing_and_care_services_are_not_tourism(self):
        for name, category in (("Casa Ejemplo Rivera", "historic_site"), ("Urb. Ficticia", "lodging"), ("Condominio Ejemplo", "historic_site"),
                               ("Hogar de Ancianos Ejemplo", "restaurant"), ("Ejemplo Tarot", "psychic_advising")):
            p = self.place(name, category)
            self.assertIn(p["withheld"], pp.NOT_TOURISM, name)
            self.assertTrue(pp.not_tourism(p, RV), name)

    def test_holiday_rentals_are_tourism_supply(self):
        for name, category in (("Casa Ejemplo", "holiday_rental_home"), ("Ejemplo Beach House", "lodging"), ("Casita Ejemplo", "hotel")):
            p = self.place(name, category)
            self.assertEqual(p["withheld"], "holiday_rental", name)
            self.assertFalse(pp.not_tourism(p, RV), name)

    def test_an_address_name_is_a_home_where_homes_are_filed_and_a_rented_unit_or_a_business_elsewhere(self):
        home = self.place("Calle Ficticia 123", "historic_site")
        self.assertEqual(home["withheld"], "address")
        self.assertTrue(pp.not_tourism(home, RV))
        for category in ("hotel", "bed_and_breakfast", "holiday_rental_home", "restaurant"):
            unit = self.place("Calle Ficticia 123", category)
            self.assertIn(unit["withheld"], ("address", "holiday_rental"), category)
            self.assertFalse(pp.not_tourism(unit, RV), category)

    def test_a_numbered_holiday_rental_filed_where_homes_are_filed_is_recorded_as_a_holiday_rental(self):
        self.assertEqual(pp.matches("Ejemplo Beach House Apt 12", "lodging", RV)[:1], ["address"])
        p = self.place("Ejemplo Beach House Apt 12", "lodging")
        self.assertEqual(p["withheld"], "holiday_rental")
        self.assertFalse(pp.not_tourism(p, RV))

    def test_a_holiday_rental_wins_over_a_weak_housing_signal(self):
        for name, category in (("Ejemplo Apartments", "lodging"), ("Ejemplo Studios", "lodging"), ("Ejemplo Surf Condo", "lodging"), ("Ejemplo Sunset House", "lodging"),
                               ("Ejemplo Lake House", "lake")):
            p = self.place(name, category)
            self.assertEqual(p["withheld"], "holiday_rental", name)
            self.assertFalse(pp.not_tourism(p, RV), name)

    def test_clear_housing_stays_residential(self):
        for name in ("Condominio Ejemplo Apartments", "Urb. Ejemplo Studios", "Residencial Ejemplo Apartments", "Villas de Ejemplo Condo", "Edificio Ejemplo Apartments"):
            p = self.place(name, "lodging")
            self.assertEqual(p["withheld"], "residential", name)
            self.assertTrue(pp.not_tourism(p, RV), name)

    def test_a_villa_is_a_subdivision_only_where_the_gazetteer_maps_one_nearby(self):
        g = json.loads((DATA / "gazetteer.json").read_text(encoding="utf-8"))
        hood = next(it for it in g["items"] if g["kinds"][it[3]] == "neighborhood" and pp.norm(it[0]).startswith("villa ") and len(pp.norm(it[0]).split()) == 2)
        near = {"oid": "x-near", "name": hood[0], "overture_category": "lodging", "lat": hood[1], "lng": hood[2]}
        far = dict(near, oid="x-far", lat=hood[1] + 0.5)
        self.assertTrue(pp.clear_housing(near["name"], "lodging", RV, near["lat"], near["lng"]))
        self.assertFalse(pp.neighbourhood_name(pp.norm(far["name"]), far["lat"], far["lng"]))

    def test_a_building_word_alone_is_not_housing_outside_lodging(self):
        self.assertIsNone(why("Edificio Ejemplo", "historic_site"))
        self.assertIsNone(why("Ejemplo Building", "monument"))
        self.assertIsNone(why("Supreme Court Ejemplo Building", "monument"))
        self.assertEqual(why("Edificio Ejemplo", "lodging"), "residential")
        self.assertEqual(why("Ejemplo Court", "historic_site"), "residential")   # a housing complex
        self.assertEqual(why("Ejemplo Apartments", "historic_site"), "residential")

    def test_a_drawn_place_is_tourism(self):
        self.assertFalse(pp.not_tourism({"withheld": None, "overture_category": "historic_site"}, RV))

    def test_a_selection_of_rows_keeps_the_access_columns_in_line(self):
        doc = {"n": 4, "ts_m": [1, 2, 3, 4], "tw_m": [5, 6, 7, 8], "tw_straight": [1, 3], "as_of": "x"}
        out = pp.permute_columns(doc, [3, 0, 2])
        self.assertEqual((out["n"], out["ts_m"], out["tw_m"], out["tw_straight"], out["as_of"]), (3, [4, 1, 3], [8, 5, 7], [0], "x"))


class Row(unittest.TestCase):
    """What build.py writes for a place (places_privacy.public_row)."""

    FULL = {"oid": "x", "name": "Ejemplo Bar 787-555-0100", "category": "GASTRONOMY", "type": "Bars", "overture_category": "bar", "municipality": "Ponce",
            "region": "Sur", "lat": 18.0, "lng": -66.6, "address": "1 Calle Ejemplo", "website": "https://example.org", "phone": "x", "email": "x",
            "socials": ["x"], "postcode": "00716", "brand": "x", "source_license": "x", "confidence": 0.9, "transit_m": 120, "transit_400m": True,
            "nearest_stop": "Parada", "barrio": "Ejemplo", "sfha": True, "withheld": None}

    def test_a_drawn_place_loses_every_contact_field_and_the_telephone_in_its_name(self):
        r = pp.public_row(dict(self.FULL))
        self.assertFalse(set(r) & pp.CONTACT_FIELDS)
        self.assertEqual(r["name"], "Ejemplo Bar")
        self.assertTrue(r["has_website"])
        self.assertNotIn("withheld", r)
        self.assertNotIn("region", r)

    def test_a_withheld_place_keeps_what_the_counts_need(self):
        r = pp.public_row({**self.FULL, "withheld": "residence", "hub_400m": True, "updated": "2026-09-14", "confidence": 0.57})
        self.assertFalse(set(r) & (pp.CONTACT_FIELDS | pp.MASKED_DROP))
        self.assertNotIn("updated", r)
        self.assertEqual(r["confidence"], 0.55)
        self.assertEqual(pp.public_row({**self.FULL, "updated": "2026-09-14", "confidence": 0.57})["confidence"], 0.57)   # a drawn place keeps both
        for k in ("municipality", "category", "type", "confidence", "sfha", "transit_m", "transit_400m", "barrio", "has_website", "hub_400m"):
            self.assertIn(k, r)
        self.assertEqual(r["withheld"], "residence")

    def test_the_confidence_step_keeps_every_slider_count(self):
        """The map's slider moves by 0.05 (index.html #conf) and every threshold the pages and access.py use is on that step."""
        html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="conf" min="0" max="1" step="0.05"', html)
        for c in range(0, 1001):
            x = c / 1000
            self.assertLessEqual(pp.conf_step(x), x)
            for t in range(21):
                self.assertEqual(x >= float(f"{t * 0.05:.2f}"), pp.conf_step(x) >= float(f"{t * 0.05:.2f}"), (x, t))
            self.assertEqual(pp.conf_step(pp.conf_step(x)), pp.conf_step(x))

    def test_the_distances_of_a_withheld_place_keep_every_threshold(self):
        """Decision 49 (2026-10-18): one value per class, on the same side of every threshold a reader uses (400, < 800, <= 800, the walk bound, 20 calls)."""
        for m in range(0, 1300):
            for near in ((True, False) if m <= 400 else (False,)):
                c = pp.coarse_transit(m, near)
                self.assertIn(c, pp.TRANSIT_CLASSES)
                self.assertEqual((c < 800, c <= 800, c <= 400), (m < 800, m <= 800, near), (m, near))
            d = pp.coarse_distance(m)
            self.assertIn(d, pp.DISTANCE_CLASSES + (99999,))
            self.assertEqual((d <= 400, d <= 800, d <= 1000), (m <= 400, m <= 800, m <= 1000), m)
        for n in range(0, 60):
            self.assertEqual((pp.coarse_calls(n) > 0, pp.coarse_calls(n) >= 20), (n > 0, n >= 20), n)
        rows = [{"withheld": "residence"}, {}, {"withheld": "address"}]
        doc = {"cap_m": 99999, "walk_bound_m": 1000, "n": 3, "ts_m": [1500, 120, 650], "ts_calls": [0, 30, 12], "ts_we": [0, 3, 1],
               "tw_m": [1500, 140, 900], "tw_calls": [0, 30, 12], "tw_we": [0, 3, 1], "tw_straight": [0]}
        pp.coarsen_columns(doc, rows)
        self.assertEqual((doc["ts_m"], doc["tw_m"], doc["ts_calls"], doc["ts_we"]), ([99999, 120, 800], [99999, 140, 1000], [0, 30, 1], [0, 3, 1]))   # row 0 has no road nearby: its walk is the straight line
        self.assertEqual(pp.column_problems(doc, rows), [])
        r = pp.public_row({**self.FULL, "withheld": "residence", "transit_m": 333, "transit_400m": True})
        self.assertEqual(r["transit_m"], 400)
        self.assertEqual(pp.public_row({**self.FULL, "transit_m": 333})["transit_m"], 333)   # a drawn place keeps its distance

    def test_the_withheld_rows_go_last_in_an_order_of_their_own(self):
        """In Overture's order a withheld row sits next to drawn rows a few hundred meters away: they are published last instead (decision 49)."""
        rows = [{"n": 1}, {"withheld": "residence", "municipality": "B"}, {"n": 2}, {"withheld": "address", "municipality": "A"}]
        perm = pp.publish_order(rows)
        self.assertEqual(perm, [0, 2, 3, 1])
        out = [rows[i] for i in perm]
        self.assertEqual(pp.order_problems(out), [])
        self.assertTrue(pp.order_problems(rows))
        doc = {"n": 4, "ts_m": [10, 20, 30, 40], "tw_straight": [1, 2]}
        self.assertEqual(pp.permute_columns(doc, perm), {"n": 4, "ts_m": [10, 30, 40, 20], "tw_straight": [1, 3]})

    def test_names_without_a_telephone_are_kept_as_written(self):
        self.assertEqual(pp.scrub_name("Ejemplo  "), "Ejemplo  ")
        self.assertEqual(pp.scrub_name("Ejemplo (787) 555-0100"), "Ejemplo")
        self.assertEqual(pp.scrub_name("Ejemplo - 787 555 0100"), "Ejemplo")


class Carry(unittest.TestCase):
    """The nightly refresh cannot measure a withheld place again: it keeps the values of the last full build (access.compute with prev)."""

    def test_the_counts_do_not_move_when_a_place_loses_its_point(self):
        stops = [stop("A", north=300, calls=25, sat=3), stop("E", north=1500, kind="rail_station", calls=80)]
        full = [place(), place(north=1400), place(north=60000)]
        res = access.compute(full, stops, operators(), AS_OF)
        access.legacy_fields(full, res)
        cols = access.columns_doc(res, "built")
        masked = [dict(p) for p in full]
        masked[1]["withheld"] = "residence"
        if res.hub400[1]:
            masked[1]["hub_400m"] = True
        masked = [pp.public_row({**p, "oid": str(i), "name": "x"}) if p.get("withheld") else p for i, p in enumerate(masked)]
        self.assertNotIn("lat", masked[1])
        again = access.compute(masked, stops, operators(), AS_OF, prev=cols)
        self.assertEqual(access.columns_doc(again, "built"), cols)
        self.assertEqual(access.area_fields(masked, again, lambda p: p["municipality"]), access.area_fields(full, res, lambda p: p["municipality"]))
        self.assertEqual(access.legacy_fields(masked, again), 0)
        self.assertNotIn("nearest_stop", masked[1])


@unittest.skipUnless((DATA / "places.json").exists(), "published files not present")
class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.places = json.loads((DATA / "places.json").read_text(encoding="utf-8"))

    def test_no_drawn_place_matches_a_pattern_without_a_review_and_no_contact_field_is_published(self):
        self.assertEqual(pp.problems(self.places, RV), [])

    def test_withheld_places_have_no_name_id_or_point(self):
        w = [p for p in self.places if p.get("withheld")]
        self.assertGreater(len(w), 0)
        self.assertTrue(all(not (set(p) & pp.MASKED_DROP) for p in w))
        self.assertTrue(all(p["withheld"] in pp.REASONS for p in w))
        self.assertTrue(all(p["confidence"] == pp.conf_step(p["confidence"]) for p in w))

    def test_the_review_names_only_public_places(self):
        self.assertTrue(all(v in pp.REASONS for v in RV["withheld"].values()), "a withheld entry is a reason, never a name")
        notes = RV.get("withheld_notes", {})
        self.assertEqual(set(notes) - {"about"}, set(RV["withheld"]), "every withheld entry says why, by id")
        drawn = {p.get("oid"): p for p in self.places if not p.get("withheld")}
        self.assertFalse(set(RV["withheld"]) & set(drawn), "a withheld id is drawn")
        stale = [k for k in RV["public"] if k not in drawn]
        self.assertEqual(stale, [], "public entries that no longer match a listing (Overture ids changed?): review them again")
        for k, v in RV["public"].items():
            self.assertEqual(drawn[k]["name"], v["name"], k)
            self.assertTrue(v["reason"])

    def test_no_published_row_is_outside_tourism_and_the_counts_follow_the_file(self):
        self.assertEqual([p for p in self.places if pp.not_tourism(p, RV)], [], "decision 47: rows that are not tourism are not published")
        self.assertEqual(pp.count_problems(self.places, DATA), [])

    def test_the_rows_still_line_up_with_the_access_columns(self):
        cols = json.loads((DATA / "place_access.json").read_text(encoding="utf-8"))
        self.assertEqual(cols["n"], len(self.places))

    def test_the_withheld_rows_are_coarsened_and_last(self):
        cols = json.loads((DATA / "place_access.json").read_text(encoding="utf-8"))
        self.assertEqual(pp.column_problems(cols, self.places), [])
        self.assertEqual(pp.order_problems(self.places), [])
        w = [p for p in self.places if p.get("withheld")]
        self.assertTrue(all(p.get("transit_m") in pp.TRANSIT_CLASSES for p in w if "transit_m" in p))

    def test_the_published_access_fields_are_what_the_code_gives(self):
        meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(access.apply_files(DATA, date.fromisoformat(meta["access"]["as_of"]), write=False, log=lambda *_: None), [])


# Published files that are public registers of place names (Census places and barrios, communities, public housing, protected areas, stops,
# libraries, the National Register, city halls...): a withheld listing that has the name of a barrio, an estate or a stop uses a public place name.
REGISTERS = ["site/data/" + f for f in ("gazetteer.json", "barrios.geojson", "comunidades.geojson", "public_housing.geojson", "housing.json", "municipios.geojson",
             "protected.geojson", "transport.json", "libraries.geojson", "historic_places.geojson", "town_halls.geojson", "fire_stations.geojson",
             "police_stations.geojson", "wcrp.geojson", "operators.json", "transit_routes.geojson", "geo/crosswalk.json",
             "lihtc.geojson")] + ["wcrp_comunidades.csv"]   # lihtc: HUD's register of tax credit housing; its care homes are never drawn (test_facilities)


def ngrams(words, wanted, firsts, longest):
    """The runs of words in `words` that are in `wanted` (a set of normalized names whose first words are `firsts`)."""
    out = set()
    for i, w in enumerate(words):
        if w in firsts:
            for k in range(1, longest + 1):
                g = " ".join(words[i:i + k])
                if g in wanted:
                    out.add(g)
    return out


@unittest.skipUnless(CACHE.exists(), "the Overture cache (cache/overture_pr_places.geojson) is not here")
class HiddenNames(unittest.TestCase):
    """No tracked text file may hold the name of a withheld place: code, docs, tests, places_review.json, HANDOFF and the generated files refer to a
    withheld place by its Overture id only. The names come from the full rows of the cache, read and decided as build.py does."""

    def test_no_withheld_name_in_a_tracked_text_file(self):
        import build
        rows, _ = build.parse_places(json.loads(CACHE.read_text(encoding="utf-8")))
        rows, _ = build.dedup(rows)
        pp.classify(rows, RV)
        hidden = {}
        for p in rows:
            if p["withheld"] and pp.norm(p["name"]):
                hidden.setdefault(pp.norm(p["name"]), p["oid"])
        self.assertGreater(len(hidden), 3000)
        longest = max(len(n.split()) for n in hidden)
        firsts = {n.split()[0] for n in hidden}
        # A withheld name that a drawn place, a public register or the rule's own word lists also use is a public name, not this place's.
        public = set()
        for p in rows:
            if not p["withheld"]:
                public |= ngrams(pp.norm(p["name"]).split(), hidden, firsts, longest)
        for f in REGISTERS:
            if (ROOT / f).exists():
                public |= ngrams(pp.norm((ROOT / f).read_text(encoding="utf-8")).split(), hidden, firsts, longest)
        vocab = " ".join(rx.pattern for rx in vars(pp).values() if isinstance(rx, re.Pattern))
        public |= ngrams(pp.norm(vocab).split(), hidden, firsts, longest)
        private = {n: oid for n, oid in hidden.items() if n not in public}
        self.assertGreater(len(private), 2500)
        firsts = {n.split()[0] for n in private}
        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8").split(chr(0))
        found = {}
        for f in tracked:
            if not f or f in REGISTERS or f == "site/data/places.json" or f.startswith("cache/"):
                continue   # places.json: places_privacy.py --check (Published) proves a withheld row has no name
            try:
                text = (ROOT / f).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue   # not a text file
            hit = ngrams(pp.norm(text).split(), private, firsts, longest)
            hit = sorted(oid for oid in (private[n] for n in hit) if oid not in WCRP_REGISTER_RUNS.get(f, ()))
            if hit:
                found[f] = hit
        self.assertEqual(found, {}, "names of withheld places (listed by Overture id) are written in these files: replace them with invented examples")


# Accepted only in these two files, by Overture id (reviewed 2026-10-19, PR #68). Each id is a withheld listing whose name equals a run of words that the
# WCRP files write from the Junta de Planificación's public register of Comunidades Especiales: a community's register name next to its municipio or barrio
# (wcrp_social.json keys each community "municipio|nombre|barrio"; wcrp_ce_assets.csv writes "nombre_lista,municipio,barrio_lista"). The text is the register's,
# not the listing's. The same run in any other tracked file still fails.
WCRP_REGISTER_RUNS = {
    "site/data/wcrp_social.json": {
        "6358dbda-f509-4dd2-875a-cba62b727018",   # municipio, then the community's register name
        "a302659a-6251-46a9-ac78-1a5946631e5f",   # register name, then its barrio
        "4a1e1538-00e4-4c9f-bd8c-7fd44a4564f5",   # register name, then its barrio
        "4d3b1f4d-92b2-466c-95f7-6dcb2dda803a",   # municipio, then the community's register name
        "bb3b2e0a-df3e-4be6-b088-79b919cc60d7",   # municipio, then the first word of the register name
        "8f733fab-7c19-4f79-a8aa-67e9924a03df",   # register name, then its barrio
        "23ee0486-2854-487f-9475-c67e99785feb",   # register name, then its barrio
    },
    "wcrp_ce_assets.csv": {   # columns nombre_lista, municipio, barrio_lista, nombre_jp, barrio_jp
        "6358dbda-f509-4dd2-875a-cba62b727018",   # municipio, then the barrio of the list
        "a302659a-6251-46a9-ac78-1a5946631e5f",   # register name (nombre_jp), then its barrio (barrio_jp)
        "4a1e1538-00e4-4c9f-bd8c-7fd44a4564f5",   # register name (nombre_jp), then its barrio (barrio_jp)
        "8f733fab-7c19-4f79-a8aa-67e9924a03df",   # register name (nombre_jp), then its barrio (barrio_jp)
        "23ee0486-2854-487f-9475-c67e99785feb",   # register name (nombre_jp), then its barrio (barrio_jp)
        "65b8c451-eede-4e1c-b186-bf23de5c69c7",   # register name, then its municipio
        "7ca408bd-8a40-4d5a-b36c-d24b700447e1",   # register name, then its municipio
        "ad3355df-9fc8-466b-b45e-1ab3599e3da1",   # register name, then its municipio
        "e2bacb69-654d-4d8e-b3a7-26312f6181f9",   # register name, then its municipio
        "e4c2dacc-9c92-41de-93d9-dc22b1ecf158",   # register name, then its municipio
        "e8672556-5d28-4ffd-a8f1-068d6f5dad84",   # register name, then its municipio
        "fc388399-e8ff-488f-b62b-7e601082455d",   # register name, then its municipio
    },
}


class Pages(unittest.TestCase):
    """The map and the 3D view draw, list, search and download only the places with a point."""

    def test_the_scripts_skip_withheld_places(self):
        js = (ROOT / "site" / "js" / "access.js").read_text(encoding="utf-8")
        self.assertIn("const placeDrawn = p => p.lat != null && p.lng != null && !p.withheld;", js)
        app = (ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
        for s in ("drawn = list.filter(placeDrawn)", "visible(p) && placeDrawn(p)), bins", "!visible(p) || !placeDrawn(p)) continue",
                  "visible(p) && placeDrawn(p)), `${name}_places.csv`", "p.sfha && placeDrawn(p)", "live.filter(p => p.has_website)"):
            self.assertIn(s, app)
        self.assertNotIn("p.website", app)
        self.assertNotIn("p.address", app)
        t3 = (ROOT / "site" / "js" / "twin3d.js").read_text(encoding="utf-8")
        self.assertIn("S.places.filter(placeDrawn).map(p => ({", t3)
        self.assertIn("!placeDrawn(p) ||", t3)

    def test_the_workflows_check_the_values(self):
        y = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("python3 places_privacy.py --check", y)
        self.assertTrue(re.search(r'"address", "website"', y))


if __name__ == "__main__":
    unittest.main()
