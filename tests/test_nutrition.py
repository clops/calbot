"""Tests for services/nutrition.py"""

from services.nutrition import calculate_targets


class TestCalculateTargets:
    def test_male_moderate_maintain(self):
        result = calculate_targets(80, 180, 30, "male", "moderate", "maintain")
        # BMR = 10*80 + 6.25*180 - 5*30 + 5 = 800 + 1125 - 150 + 5 = 1780
        # TDEE = 1780 * 1.55 = 2759
        assert result["target_calories"] == 2759
        assert result["target_proteins"] == 160  # 2 * 80
        assert result["target_fats"] == 77  # round(0.25 * 2759 / 9)
        # carbs = (2759 - 160*4 - 77*9) / 4 = (2759 - 640 - 693) / 4 = 356.5
        assert result["target_carbs"] == 356

    def test_female_sedentary_maintain(self):
        result = calculate_targets(60, 165, 25, "female", "sedentary", "maintain")
        # BMR = 10*60 + 6.25*165 - 5*25 - 161 = 600 + 1031.25 - 125 - 161 = 1345.25
        # TDEE = 1345.25 * 1.2 = 1614.3
        assert result["target_calories"] == 1614
        assert result["target_proteins"] == 120  # 2 * 60

    def test_lose_subtracts_500(self):
        maintain = calculate_targets(80, 180, 30, "male", "moderate", "maintain")
        lose = calculate_targets(80, 180, 30, "male", "moderate", "lose")
        assert maintain["target_calories"] - lose["target_calories"] == 500

    def test_gain_adds_500(self):
        maintain = calculate_targets(80, 180, 30, "male", "moderate", "maintain")
        gain = calculate_targets(80, 180, 30, "male", "moderate", "gain")
        assert gain["target_calories"] - maintain["target_calories"] == 500

    def test_activity_levels_increase_calories(self):
        sed = calculate_targets(80, 180, 30, "male", "sedentary", "maintain")
        light = calculate_targets(80, 180, 30, "male", "light", "maintain")
        mod = calculate_targets(80, 180, 30, "male", "moderate", "maintain")
        active = calculate_targets(80, 180, 30, "male", "active", "maintain")
        assert sed["target_calories"] < light["target_calories"] < mod["target_calories"] < active["target_calories"]

    def test_carbs_clamped_to_zero(self):
        # Very light person losing weight — could get negative carbs
        result = calculate_targets(30, 150, 20, "female", "sedentary", "lose")
        assert result["target_carbs"] >= 0

    def test_returns_all_keys(self):
        result = calculate_targets(70, 170, 40, "male", "light", "maintain")
        assert set(result.keys()) == {"target_calories", "target_proteins", "target_fats", "target_carbs"}

    def test_all_values_are_int(self):
        result = calculate_targets(75.5, 172.3, 33, "female", "moderate", "gain")
        for v in result.values():
            assert isinstance(v, int)
