import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_integrator.parsers import (
    parse_interest_values_report,
    parse_tenmei_report,
)
from career_integrator.prompt import build_user_message, resolve_name

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
INTEREST = (SAMPLES / "interest_values_report.txt").read_text(encoding="utf-8")
TENMEI = (SAMPLES / "tenmei_report.txt").read_text(encoding="utf-8")


class InterestValuesParserTest(unittest.TestCase):
    def setUp(self):
        self.r = parse_interest_values_report(INTEREST)

    def test_name_and_date(self):
        self.assertEqual(self.r.name, "まつい")
        self.assertEqual(self.r.created_date, "2026/8/30")

    def test_riasec_counts(self):
        self.assertEqual(self.r.riasec_counts["I型"], 6)
        self.assertEqual(self.r.riasec_counts["A型"], 4)
        self.assertEqual(self.r.riasec_counts["E型"], 2)
        self.assertEqual(self.r.riasec_counts["R型"], 0)

    def test_riasec_selected(self):
        self.assertEqual(self.r.riasec_selected, ["I型", "A型", "E型"])

    def test_values_top3(self):
        self.assertEqual(len(self.r.values_top3), 3)
        self.assertTrue(self.r.values_top3[0].startswith("美しさ"))
        self.assertTrue(self.r.values_top3[1].startswith("創造性"))
        self.assertTrue(self.r.values_top3[2].startswith("社会貢献"))

    def test_phrases(self):
        self.assertIn("美しい社会の実現", self.r.intersection_phrase)
        self.assertIn("チームで課題を解決", self.r.career_direction)
        self.assertIsNotNone(self.r.one_line_summary)

    def test_small_steps(self):
        self.assertEqual(self.r.small_steps[0], "社会課題の発見と理解")
        self.assertEqual(len(self.r.small_steps), 3)

    def test_ai_analysis(self):
        self.assertIsNotNone(self.r.ai_analysis)
        self.assertIn("論理と感性を統合する「美学」", self.r.ai_analysis)
        # 末尾の罫線はトリムされている
        self.assertFalse(self.r.ai_analysis.rstrip().endswith("═"))


class TenmeiParserTest(unittest.TestCase):
    def setUp(self):
        self.r = parse_tenmei_report(TENMEI)

    def test_identity(self):
        self.assertEqual(self.r.name, "ひでと")
        self.assertEqual(self.r.birth_date, "1967年11月11日")

    def test_type_and_strength(self):
        self.assertTrue(self.r.tenmei_type.startswith("土の食神タイプ"))
        self.assertEqual(self.r.core_strength, "創造性と人を喜ばせる才能")

    def test_work_tendency(self):
        self.assertIn("楽しみながら作ること", self.r.work_tendency)

    def test_suited_fields(self):
        self.assertEqual(len(self.r.suited_fields), 6)
        self.assertEqual(self.r.suited_fields[0], "料理人・フードクリエイター")
        self.assertEqual(self.r.suited_fields[-1], "音楽家・俳優")

    def test_fulfillment_and_inquiry(self):
        self.assertIn("人を喜ばせたとき", self.r.source_of_fulfillment)
        self.assertIn("遊び", self.r.self_inquiry)
        # 末尾URL行を巻き込んでいない
        self.assertNotIn("vercel", self.r.self_inquiry)


class PromptTest(unittest.TestCase):
    def test_resolve_name_prefers_tenmei(self):
        iv = parse_interest_values_report(INTEREST)
        t = parse_tenmei_report(TENMEI)
        self.assertEqual(resolve_name(iv, t), "ひでと")
        self.assertEqual(resolve_name(iv, t, "山田"), "山田")

    def test_user_message_contains_both_raws_and_summary(self):
        iv = parse_interest_values_report(INTEREST)
        t = parse_tenmei_report(TENMEI)
        msg = build_user_message(iv, t, name="ひでと")
        self.assertIn("<report_interest_values>", msg)
        self.assertIn("<report_tenmei>", msg)
        self.assertIn("土の食神タイプ", msg)
        self.assertIn("価値観 第1位: 美しさ", msg)
        self.assertIn("料理人・フードクリエイター", msg)
        # 原文が省略されていない
        self.assertIn("【AI キャリア分析】", msg)


class RobustnessTest(unittest.TestCase):
    def test_empty_inputs_do_not_raise(self):
        iv = parse_interest_values_report("")
        t = parse_tenmei_report("")
        self.assertIsNone(iv.name)
        self.assertEqual(iv.riasec_selected, [])
        self.assertIsNone(t.tenmei_type)
        self.assertEqual(resolve_name(iv, t), "ご本人")

    def test_full_width_colon_variant(self):
        t = parse_tenmei_report("■ お名前：テスト太郎\n■ 生年月日：2000年1月1日\n")
        self.assertEqual(t.name, "テスト太郎")


if __name__ == "__main__":
    unittest.main()
