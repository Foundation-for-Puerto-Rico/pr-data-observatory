"""A licence line shown to visitors says 'public domain' only where the data contract (dictionary_src/sources.json) says it.

The pages show each source's licence from the data files (economy_series.json, housing_series.json, meta.json). The contract was written from the sources' own terms; the texts in the
builders were not, and two reviews of pull request 3 found lines that claimed more than the contract (USAspending, the Census Bureau's products, FEMA, the FAA). Add the source to
the table below when a builder gets a new one: the test fails for a source it does not know, so that somebody decides what the contract says about it.

  python -m unittest tests.test_licence_text
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"

# the key a data file uses for a source -> the id of the contract record that describes the same thing
CONTRACT = {
    "economy_series.json": {"qcew": "bls_qcew", "laus": "bls_laus", "acs": "acs5", "usaspending": "usaspending", "openfema": "openfema", "pep": "census_pep", "cpi": "bls_cpi", "overture": "overture", "ppr": "ppr_type1", "fac": "fac", "nmtc": "nmtc"},
    "housing_series.json": {"pep": "census_pep", "census": "census_decennial", "acs": "acs5", "fema": "openfema", "derived": "fpr_method"},
    "health_series.json": {"hrsa_sites": "hrsa_sites", "hrsa_hpsa": "hrsa_hpsa"},
    "care_series.json": {"cms_provider_data": "cms_provider_data", "hrsa_sites": "hrsa_sites", "osm": "osm", "census_tiger": "census_tiger"},
    "medicare_series.json": {"cms_medicare_enrollment": "cms_medicare_enrollment"},
    "infrastructure_series.json": {"epa_echo_sdwa": "epa_echo_sdwa", "epa_echo_cwa": "epa_echo_cwa", "epa_echo_caa": "epa_echo_caa", "epa_echo_rcra": "epa_echo_rcra", "epa_echo_all": "epa_echo_all", "epa_tri": "epa_tri", "eia_860m": "eia_860m"},
    "bridges_series.json": {"fhwa_nbi": "fhwa_nbi"},
    "traffic_series.json": {"fhwa_hpms": "fhwa_hpms"},
    "crashes_series.json": {"nhtsa_fars": "nhtsa_fars", "census_pep": "census_pep", "fhwa_hpms": "fhwa_hpms"},
    "environment_series.json": {"fema_nri": "fema_nri", "usgs_slope_failures": "usgs_slope_failures", "usfws_nwi": "usfws_nwi"},
    "hazard_series.json": {"census_cre": "census_cre", "usgs_comcat": "usgs_comcat"},
    "gateway_series.json": {"bts_t100": "bts_t100", "faa_enplanements": "faa_enplanements", "bts_ncfo": "bts_ncfo"},
    "community_series.json": {"nps_nrhp": "nps_nrhp", "samhsa_nsumhss": "samhsa_nsumhss"},
    "facility_series.json": {"hud_public_housing": "hud_public_housing", "hud_lihtc": "hud_lihtc", "usgs_structures": "usgs_structures", "osm": "osm", "usac_erate": "usac_erate"},
    "nonprofit_series.json": {"irs_eo_bmf": "irs_eo_bmf", "census_zcta_county": "census_zcta_county"},
    "conditions_series.json": {k: k for k in ("epa_tri", "epa_frs", "epa_attains", "epa_greenbook", "epa_lmop", "hud_chas", "census_tiger_lines", "cms_provider_data", "hhs_hospital_capacity", "osm", "census_tiger")},
    "landslide_series.json": {"usgs_landslide_map": "usgs_landslide_map", "census_tiger": "census_tiger"},
    "heat_series.json": {"usgs_landsat_c2_st": "usgs_landsat_c2_st", "census_tiger": "census_tiger"},
    "vegetation_series.json": {"copernicus_sentinel2_l2a": "copernicus_sentinel2_l2a", "census_tiger": "census_tiger"},
    "buildings_series.json": {"overture_buildings": "overture_buildings", "census_tiger": "census_tiger"},
    "fires_series.json": {"nasa_firms": "nasa_firms", "census_tiger": "census_tiger"},
    "night_heat_series.json": {"nasa_ecostress_lste": "nasa_ecostress_lste", "census_tiger": "census_tiger"},
    "climb_series.json": {"usgs_3dep_13": "usgs_3dep_13", "census_tiger": "census_tiger"},
    "slope_series.json": {"usgs_3dep_13": "usgs_3dep_13", "census_tiger": "census_tiger"},
    "nightlights_series.json": {"nasa_black_marble": "nasa_black_marble", "census_tiger": "census_tiger"},
    "broadband_series.json": {"fcc_bdc": "fcc_bdc", "census_tiger": "census_tiger"},
    "energy_series.json": {"luma_bureau": "luma_bureau", "acs": "acs5"},
    "commuting_series.json": {"commuting_flows": "census_commuting_flows", "census_2020": "census_decennial"},
    "svi_series.json": {"cdc_svi": "cdc_svi"},
    "credit_series.json": {"fdic_sod": "fdic_sod", "hmda": "hmda"},
    "drought_series.json": {"usdm": "usdm"},
    "storm_recovery_series.json": {"nasa_black_marble": "nasa_black_marble", "census_tiger": "census_tiger"},
    "degrees_series.json": {"nces_ipeds": "nces_ipeds"},
    "school_conditions_series.json": {"urban_crdc": "urban_crdc", "urban_ccd": "urban_ccd"},
    "proficiency_series.json": {"urban_edfacts": "urban_edfacts", "urban_ccd": "urban_ccd"},
    "providers_series.json": {"cms_nppes": "cms_nppes", "census_zcta_county": "census_zcta_county"},
    "cutoff_series.json": {"osm": "osm", "fema_nfhl": "fema_nfhl", "fhwa_nbi": "fhwa_nbi", "census_tiger": "census_tiger"},
    "essentials_series.json": {"overture": "overture", "usac_erate": "usac_erate", "usgs_structures": "usgs_structures", "osm": "osm", "census_tiger": "census_tiger"},
    "facility_exposure_series.json": {"fema_nfhl": "fema_nfhl", "noaa_slr": "noaa_slr", "usgs_landslide_map": "usgs_landslide_map", "fx_layers": "fpr_twin"},
    "opportunity_zones.json": {"treasury_oz": "treasury_oz", "census_tiger": "census_tiger", "census_cartographic": "census_cartographic"},
    "inflation.json": {"dtrh": "dtrh_cpi", "dtrh_csv": "dtrh_cpi", "bls": "bls_cpi", "cleveland": "frbc_inflation_expectations", "spf": "frbp_spf", "acs": "acs1"},
    "meta.json": {"overture": "overture", "fema": "fema_nfhl", "padus": "padus", "census": "census_tiger", "census_shore": "census_tiger", "noaa_slr": "noaa_slr", "osm": "osm", "ati_gtfs": "ati_gtfs",
                  "osm_transport": "osm", "faa_airports": "faa_airports", "uber": "uber", "muni_gtfs": "muni_gtfs", "ntd": "ntd", "osm_routes": "osm", "census_blocks": "census_tiger", "hurdat2": "nhc_hurdat2",
                  "census2010": "census_tiger", "acs_latest": "acs5", "acs_2012": "acs5", "fpr_housing_2023": "fpr_housing_2023", "nalcab": "fpr_housing_2023", "census_barrios": "census_tiger",
                  "put2015": "jp_put2015", "calificacion": "jp_calificacion", "osm_roads": "osm", "housing_pep": "census_pep", "housing_census": "census_decennial", "housing_acs": "acs5",
                  "housing_fema": "openfema", "housing_derived": "fpr_method",
                  "economy_qcew": "bls_qcew", "economy_laus": "bls_laus", "economy_acs": "acs5", "economy_usaspending": "usaspending", "economy_openfema": "openfema", "economy_pep": "census_pep",
                  "economy_cpi": "bls_cpi", "economy_overture": "overture", "economy_ppr": "ppr_type1", "economy_fac": "fac", "economy_nmtc": "nmtc"},   # the last eleven: what a full build of meta.json adds from economy_series.py
}


class LicenceText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = json.loads((ROOT / "dictionary_src" / "sources.json").read_text(encoding="utf-8"))
        cls.contract = {k: v for k, v in s.items() if not k.startswith("_")}

    def test_every_source_a_data_file_names_is_in_the_table(self):
        for name, ids in CONTRACT.items():
            srcs = json.loads((DATA / name).read_text(encoding="utf-8"))["sources"]
            self.assertEqual(sorted(set(srcs) - set(ids)), [], f"{name}: sources the test does not know; say which contract record they are")
            for k, cid in ids.items():
                self.assertIn(cid, self.contract, f"{name}: {k} -> {cid} is not a record of sources.json")

    def test_a_licence_line_says_public_domain_only_where_the_contract_does(self):
        for name, ids in CONTRACT.items():
            srcs = json.loads((DATA / name).read_text(encoding="utf-8"))["sources"]
            for k, s in srcs.items():
                shown = (s.get("license") or "").lower()
                said = (self.contract[ids[k]].get("licence") or "").lower()
                if "public domain" in shown:
                    self.assertIn("public domain", said, f"{name} {k} says {s['license']!r}; the contract says {self.contract[ids[k]].get('licence')!r}")


if __name__ == "__main__":
    unittest.main()
