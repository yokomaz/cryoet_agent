from __future__ import annotations

import unittest

from cryoet_agent.skills.loader import load_builtin_skills, select_skills


class SkillLoaderTests(unittest.TestCase):
    def test_builtin_skills_load(self) -> None:
        skills = load_builtin_skills()
        self.assertIn("warp", skills)
        self.assertIn("sta", skills)

    def test_skill_selection_uses_goal_keywords(self) -> None:
        skills = load_builtin_skills()
        selected = select_skills(
            "I want to reconstruct tomograms and then do STA on this dataset.",
            skills,
        )
        names = {skill.metadata.name for skill in selected}
        self.assertIn("reconstruct_tomogram", names)
        self.assertIn("sta", names)


if __name__ == "__main__":
    unittest.main()

