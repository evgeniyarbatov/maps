import unittest

from scripts.text_utils import normalize_description, to_english


class ToEnglishTests(unittest.TestCase):
    def test_transliterates_non_ascii(self) -> None:
        self.assertEqual(to_english("Núi Đinh"), "Nui Dinh")

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(to_english(""), "")

    def test_strips_whitespace(self) -> None:
        self.assertEqual(to_english("  plain text  "), "plain text")


class NormalizeDescriptionTests(unittest.TestCase):
    def test_strips_quotes_and_trailing_punctuation(self) -> None:
        self.assertEqual(normalize_description('"Buddhist temple."'), "Buddhist temple")

    def test_strips_banned_prefix(self) -> None:
        self.assertEqual(normalize_description("Visit old pagoda"), "old pagoda")
        self.assertEqual(normalize_description("Walk summit"), "summit")

    def test_takes_first_sentence_only(self) -> None:
        self.assertEqual(
            normalize_description("Forest viewpoint. Great sunset spot."), "Forest viewpoint"
        )

    def test_takes_text_before_semicolon(self) -> None:
        self.assertEqual(normalize_description("Old pagoda; built in 1900"), "Old pagoda")

    def test_truncates_to_max_words(self) -> None:
        long_phrase = " ".join(f"word{i}" for i in range(12))
        result = normalize_description(long_phrase)
        self.assertEqual(len(result.split()), 8)

    def test_empty_input_returns_empty(self) -> None:
        self.assertEqual(normalize_description(""), "")

    def test_only_punctuation_returns_empty(self) -> None:
        self.assertEqual(normalize_description('"..."'), "")


if __name__ == "__main__":
    unittest.main()
