from __future__ import annotations

import unittest

from geowatch.ucdp_bulk import (
    aggregate_actor_profiles,
    aggregate_armed_conflict_cases,
    enrich_cases_with_termination,
    termination_outcomes,
)


class UCDPCodebookAlignmentTests(unittest.TestCase):
    def test_conflict_years_split_into_continuous_episodes(self):
        rows = [
            {
                "conflict_id": "100",
                "year": "2018",
                "location": "State A",
                "side_a": "Government of State A",
                "side_b": "Rebel Movement",
                "region": "4",
                "type_of_conflict": "3",
                "start_date2": "2018-02-03",
                "start_prec2": "1",
                "ep_end": "1",
                "ep_end_date": "2018-11-20",
                "ep_end_prec": "1",
                "intensity_level": "1",
                "version": "26.1",
            },
            {
                "conflict_id": "100",
                "year": "2021",
                "location": "State A",
                "side_a": "Government of State A",
                "side_b": "Rebel Movement",
                "region": "4",
                "type_of_conflict": "4",
                "start_date2": "2021-03-10",
                "start_prec2": "1",
                "ep_end": "0",
                "ep_end_date": "",
                "intensity_level": "2",
                "version": "26.1",
            },
            {
                "conflict_id": "100",
                "year": "2022",
                "location": "State A",
                "side_a": "Government of State A",
                "side_b": "Rebel Movement",
                "region": "4",
                "type_of_conflict": "4",
                "start_date2": "2021-03-10",
                "start_prec2": "1",
                "ep_end": "1",
                "ep_end_date": "2022-09-01",
                "ep_end_prec": "2",
                "intensity_level": "1",
                "version": "26.1",
            },
        ]
        cases = aggregate_armed_conflict_cases(rows)
        self.assertEqual(2, len(cases))
        self.assertEqual("ucdp_conflict_100_episode_1", cases[0]["case_id"])
        self.assertEqual([2018], cases[0]["active_years"])
        self.assertEqual("2018-11-20", cases[0]["end"])
        self.assertEqual("ucdp_conflict_100_episode_2", cases[1]["case_id"])
        self.assertEqual([2021, 2022], cases[1]["active_years"])
        self.assertEqual("2022-09-01", cases[1]["end"])
        self.assertEqual(["ucdp_type_4"], cases[1]["types"])

    def test_actor_parser_uses_namedata_and_preserves_lineage(self):
        rows = [{
            "ActorId": "7332",
            "NameData": "Example Movement",
            "NameOrig": "Original Movement",
            "NameOrigFull": "Original Full Name",
            "NameOrigFullEng": "Original Full Name English",
            "NameChange": "1",
            "NewName": "Example Movement",
            "Org": "1",
            "ConflictId": "100, 200",
            "DyadId": "300, 400",
            "PrimaryParty": "1",
            "Splinter": "1",
            "NamePrev": "Parent Movement",
            "ActorIdPrev": "7000",
            "SplitTemp": "0",
            "Alliance": "1",
            "NameAlliance": "Alliance Name",
            "ActorIdAlliance": "8000",
            "JoinGroup": "0",
            "Location": "State A, State B",
            "Region": "4",
            "Version": "26.1",
        }]
        profiles = aggregate_actor_profiles(rows)
        self.assertEqual(1, len(profiles))
        profile = profiles[0]
        self.assertEqual("Example Movement", profile["name"])
        self.assertIn("Original Movement", profile["aliases"])
        self.assertIn("Alliance Name", profile["aliases"])
        self.assertEqual(["100", "200"], profile["conflict_ids"])
        self.assertTrue(profile["primary_party"])
        self.assertTrue(profile["lineage"]["splinter"])
        self.assertEqual("7000", profile["lineage"]["parent_actor_id"])
        self.assertEqual("8000", profile["lineage"]["alliance_actor_id"])

    def test_termination_parser_uses_conflict_episode_fields(self):
        rows = [
            {
                "conflict_id": "100",
                "c_epno": "1",
                "c_outcome": "2",
                "c_ependdate": "2018-11-20",
                "c_ependprec": "1",
                "version": "4-2024",
            },
            {
                "conflict_id": "100",
                "c_epno": "2",
                "c_outcome": "1",
                "c_ependdate": "2022-09-01",
                "c_ependprec": "2",
                "version": "4-2024",
            },
        ]
        terminations = termination_outcomes(rows)
        self.assertEqual("ceasefire", terminations[("100", 1)]["outcome_tag"])
        self.assertEqual("peace_agreement", terminations[("100", 2)]["outcome_tag"])
        cases = [
            {"case_id": "a", "ucdp_conflict_id": "100", "ucdp_episode_no": 1, "end": None, "outcome_tags": [], "source_ids": []},
            {"case_id": "b", "ucdp_conflict_id": "100", "ucdp_episode_no": 2, "end": None, "outcome_tags": [], "source_ids": []},
        ]
        enriched = enrich_cases_with_termination(cases, terminations)
        self.assertEqual("2018-11-20", enriched[0]["end"])
        self.assertIn("ceasefire", enriched[0]["outcome_tags"])
        self.assertEqual("2022-09-01", enriched[1]["end"])
        self.assertIn("peace_agreement", enriched[1]["outcome_tags"])

    def test_column_normalization_handles_spaces_and_underscores(self):
        rows = [{
            "conflict id": "9",
            "c epno": "3",
            "c outcome": "5",
            "c ependdate": "2001-12-31",
            "c ependprec": "5",
        }]
        parsed = termination_outcomes(rows)
        self.assertEqual("low_activity", parsed[("9", 3)]["outcome_tag"])
        self.assertEqual(5, parsed[("9", 3)]["end_precision"])


if __name__ == "__main__":
    unittest.main()
