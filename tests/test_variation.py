import unittest

from variation import build_variations, join_prompt, parse_lines


SHOTS = """\
close-up portrait
upper body shot
cowboy shot
full body shot
"""

EXPRESSIONS = """\
gentle smile
laughing
surprised expression
embarrassed expression
"""


class VariationTests(unittest.TestCase):
    def test_parse_lines_removes_comments_blanks_and_duplicates(self):
        value = "one\n\n# ignored\n two \none\n"
        self.assertEqual(parse_lines(value), ["one", "two"])

    def test_join_prompt_normalizes_commas(self):
        self.assertEqual(
            join_prompt("masterpiece,", ", close-up", " smile "),
            "masterpiece, close-up, smile",
        )

    def test_four_variations_are_deterministic_and_unique(self):
        first = build_variations(
            "masterpiece, 1girl",
            SHOTS,
            EXPRESSIONS,
            4,
            12345,
        )
        second = build_variations(
            "masterpiece, 1girl",
            SHOTS,
            EXPRESSIONS,
            4,
            12345,
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)
        self.assertEqual(len({(item.shot, item.expression) for item in first}), 4)
        self.assertEqual(len({item.seed for item in first}), 4)

    def test_count_cannot_exceed_combinations(self):
        with self.assertRaisesRegex(ValueError, "only 1"):
            build_variations("base", "shot", "face", 2, 0)


if __name__ == "__main__":
    unittest.main()
