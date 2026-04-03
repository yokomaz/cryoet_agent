from __future__ import annotations

from dataclasses import dataclass

from cryoet_agent.agent.local_model import build_model_client
from cryoet_agent.agent.prompts import build_planner_prompt
from cryoet_agent.agent.schemas import DatasetState, PlanningRequest, Skill, WorkflowPlan, WorkflowStep
from cryoet_agent.introspection.scanner import scan_workspace
from cryoet_agent.skills.loader import load_builtin_skills, select_skills


GOAL_PATTERNS = {
    "reconstruct_tomogram": ("reconstruct", "tomogram", "reconstruction"),
    "particle_picking": ("pick", "particle"),
    "denoising": ("denois",),
    "ctf_correction": ("ctf",),
    "missing_wedge_compensation": ("missing wedge",),
    "sta": ("sta", "subtomogram average", "subtomogram averaging"),
}


@dataclass
class PlanningResult:
    plan: WorkflowPlan
    dataset_state: DatasetState
    skills: list[Skill]


class CryoETPlanner:
    def __init__(self, model_provider: str | None = None):
        self.skill_map = load_builtin_skills()
        self.model_client = build_model_client(model_provider)

    def plan(self, request: PlanningRequest) -> PlanningResult:
        dataset_state = scan_workspace(request.dataset_path)
        skills = select_skills(request.user_message, self.skill_map)
        draft = self._build_rule_based_plan(request, dataset_state, skills)
        prompt = build_planner_prompt(request.user_message, dataset_state, skills, draft)
        generated = self.model_client.generate_plan(prompt, draft)
        plan = generated.plan.model_copy(update={"generated_by": generated.provider})
        if not plan.relevant_skills:
            plan.relevant_skills = [skill.metadata.name for skill in skills]
        return PlanningResult(plan=plan, dataset_state=dataset_state, skills=skills)

    def _build_rule_based_plan(
        self,
        request: PlanningRequest,
        dataset_state: DatasetState,
        skills: list[Skill],
    ) -> WorkflowPlan:
        goals = self._normalize_goals(request.user_message)
        findings = self._summarize_findings(dataset_state)
        assumptions = list(dataset_state.notes)
        unresolved = list(dataset_state.missing_requirements) + list(dataset_state.warnings)

        steps: list[WorkflowStep] = []
        for goal in goals:
            steps.extend(self._build_steps_for_goal(goal, dataset_state, skills))

        if not goals:
            unresolved.append(
                "The requested scientific objective could not be normalized. Try naming tasks such as tomogram reconstruction, denoising, particle picking, or STA."
            )

        if not steps:
            steps.append(
                WorkflowStep(
                    step_id="clarify-1",
                    title="Clarify dataset and objective",
                    purpose="Collect enough metadata to produce a reliable CryoET workflow.",
                    software=[],
                    inputs=["workspace inventory"],
                    outputs=["clarified project definition"],
                    suggested_parameters={},
                    rationale="The current workspace summary does not yet support a concrete workflow.",
                    checks=[
                        "Confirm whether the dataset contains raw movies, tilt series, or already reconstructed tomograms.",
                        "Provide microscope metadata such as tilt angles, pixel size, and dose information if available.",
                    ],
                    risks=["Planning downstream CryoET steps from incomplete metadata can send the user into the wrong software path."],
                    status="blocked",
                )
            )

        summary = self._build_summary(goals, dataset_state)
        alternatives = self._build_alternatives(goals, skills)
        return WorkflowPlan(
            goal=request.user_message,
            normalized_goals=goals,
            summary=summary,
            workspace=dataset_state.workspace,
            dataset_path=dataset_state.requested_path,
            assumptions=assumptions,
            findings=findings,
            steps=self._deduplicate_steps(steps),
            alternative_options=alternatives,
            unresolved_questions=self._unique(unresolved),
            relevant_skills=[skill.metadata.name for skill in skills],
        )

    def _normalize_goals(self, user_message: str) -> list[str]:
        lowered = user_message.lower()
        goals = []
        for normalized, patterns in GOAL_PATTERNS.items():
            if any(pattern in lowered for pattern in patterns):
                goals.append(normalized)
        return goals

    def _summarize_findings(self, state: DatasetState) -> list[str]:
        findings = []
        if state.inferred_stage:
            findings.append(f"Inferred dataset stage: {state.inferred_stage}.")
        if state.detected_modalities:
            findings.append(f"Detected asset types: {', '.join(state.detected_modalities)}.")
        if state.assets:
            findings.append(f"Scanned {len(state.assets)} files under `{state.requested_path}`.")
        return findings

    def _build_summary(self, goals: list[str], state: DatasetState) -> str:
        goal_text = ", ".join(goals) if goals else "CryoET planning"
        stage = state.inferred_stage or "unclear dataset stage"
        return (
            f"This plan targets {goal_text} based on a workspace that currently looks like {stage}. "
            "It prioritizes beginner-safe steps, highlights missing metadata, and keeps conditional stages explicit."
        )

    def _build_alternatives(self, goals: list[str], skills: list[Skill]) -> list[str]:
        alternatives = []
        skill_names = {skill.metadata.name for skill in skills}
        if "reconstruct_tomogram" in goals and {"aretomo", "imod"} <= skill_names:
            alternatives.append("For tomogram reconstruction, AreTomo is the simpler beginner path, while IMOD gives more manual control and inspection.")
        if "sta" in goals and {"relion_sta", "dynamo_sta"} & skill_names:
            alternatives.append("For STA, RELION offers a more standardized refinement path, while Dynamo is often favored for flexible subtomogram workflows.")
        return alternatives

    def _build_steps_for_goal(
        self,
        goal: str,
        state: DatasetState,
        skills: list[Skill],
    ) -> list[WorkflowStep]:
        if goal == "reconstruct_tomogram":
            return self._steps_for_reconstruction(state)
        if goal == "particle_picking":
            return self._steps_for_particle_picking(state)
        if goal == "denoising":
            return self._steps_for_denoising(state)
        if goal == "ctf_correction":
            return self._steps_for_ctf(state)
        if goal == "missing_wedge_compensation":
            return self._steps_for_missing_wedge(state)
        if goal == "sta":
            return self._steps_for_sta(state)
        return []

    def _steps_for_reconstruction(self, state: DatasetState) -> list[WorkflowStep]:
        steps = []
        if "raw_movie" in state.detected_modalities:
            steps.append(
                WorkflowStep(
                    step_id="recon-1",
                    title="Motion-correct raw tilt movies",
                    purpose="Reduce beam-induced motion before any downstream CryoET estimation.",
                    software=["Warp"],
                    inputs=["raw tilt movies"],
                    outputs=["motion-corrected tilt series"],
                    suggested_parameters={
                        "frame_alignment": "Use conservative patch-based alignment matched to detector mode.",
                        "binning": "Start with mild binning if file size or SNR is limiting.",
                    },
                    rationale="Warp is a common entry point for raw movie preprocessing and is beginner-friendly for motion correction setup.",
                    checks=["Confirm detector mode and verify that motion-corrected sums are generated for each tilt."],
                    risks=["Incorrect gain or frame grouping will propagate errors into alignment and reconstruction."],
                )
            )
        steps.append(
            WorkflowStep(
                step_id="recon-2",
                title="Prepare tilt metadata and estimate CTF",
                purpose="Associate each tilt image with acquisition metadata and estimate defocus or CTF quality.",
                software=["Warp"],
                inputs=["motion-corrected tilt series", "metadata files such as .mdoc or .star"],
                outputs=["annotated tilt series with CTF estimates"],
                suggested_parameters={
                    "tilt_metadata": "Ensure tilt angle ordering matches acquisition order.",
                    "ctf_resolution_limit": "Use a conservative limit if SNR is low or defocus estimates are unstable.",
                },
                rationale="CTF information and tilt-angle consistency are prerequisites for reliable tomogram reconstruction.",
                checks=["Verify that tilt angles, dose, and pixel size are available or added manually before proceeding."],
                risks=["Missing or wrong angle ordering can invalidate all downstream geometry."],
                status="conditional" if "No metadata" in " ".join(state.missing_requirements) else "ready",
            )
        )
        steps.append(
            WorkflowStep(
                step_id="recon-3",
                title="Align the tilt series and reconstruct the tomogram",
                purpose="Estimate image geometry across tilts and reconstruct the 3D tomogram volume.",
                software=["AreTomo", "IMOD"],
                inputs=["tilt series", "tilt-angle metadata", "pixel size"],
                outputs=["aligned tilt series", "reconstructed tomogram"],
                suggested_parameters={
                    "tilt_axis": "Verify from microscope geometry or alignment diagnostics before final reconstruction.",
                    "out_bin": "Start with binned reconstruction for QC, then repeat at target sampling if needed.",
                    "vol_z": "Set thickness to cover the specimen plus margin, not the full empty ice volume.",
                },
                rationale="AreTomo provides a simpler beginner path, while IMOD remains a strong option when more manual inspection is needed.",
                checks=["Inspect alignment residuals and tomogram slices before committing to downstream analysis."],
                risks=["Wrong tilt axis or thickness settings can blur the reconstruction and waste downstream work."],
                status="conditional" if state.missing_requirements else "ready",
            )
        )
        return steps

    def _steps_for_particle_picking(self, state: DatasetState) -> list[WorkflowStep]:
        status = "ready" if "tomogram" in state.detected_modalities else "conditional"
        prerequisite = []
        if "tomogram" not in state.detected_modalities:
            prerequisite.append(
                WorkflowStep(
                    step_id="pick-0",
                    title="Obtain a tomogram first",
                    purpose="Particle picking requires a reconstructed tomogram or equivalent 3D volume.",
                    software=["AreTomo", "IMOD"],
                    inputs=["tilt series or raw movies"],
                    outputs=["tomogram"],
                    suggested_parameters={},
                    rationale="Picking is not meaningful before 3D reconstruction is available.",
                    checks=["Complete alignment and reconstruction QC before attempting picks."],
                    risks=["Picking on an unvalidated or low-quality volume will create noisy coordinates."],
                    status="conditional",
                )
            )
        prerequisite.append(
            WorkflowStep(
                step_id="pick-1",
                title="Choose a particle picking strategy",
                purpose="Generate candidate particle coordinates for later extraction and refinement.",
                software=["Warp", "RELION", "manual annotation"],
                inputs=["tomogram"],
                outputs=["particle coordinates"],
                suggested_parameters={
                    "picking_strategy": "Start with manual seed points or low-stringency template matching if no pretrained model is available.",
                    "box_size": "Choose a box that fully contains the particle with margin.",
                },
                rationale="Beginners benefit from a conservative picking pass that can be manually reviewed before large-scale extraction.",
                checks=["Inspect coordinate overlays in orthoslices to ensure particles land on real structures."],
                risks=["Over-aggressive picking thresholds will inflate false positives."],
                status=status,
            )
        )
        return prerequisite

    def _steps_for_denoising(self, state: DatasetState) -> list[WorkflowStep]:
        return [
            WorkflowStep(
                step_id="denoise-1",
                title="Denoise the tomogram after reconstruction QC",
                purpose="Improve interpretability for visualization or downstream segmentation while preserving a raw reference volume.",
                software=["cryoCARE or comparable denoising workflow"],
                inputs=["validated tomogram"],
                outputs=["denoised tomogram"],
                suggested_parameters={
                    "training_split": "Use an even/odd or otherwise independent split if the denoising method requires paired training.",
                    "preserve_raw": "Keep the original tomogram alongside any denoised output.",
                },
                rationale="Denoising is helpful for interpretation, but the raw tomogram should remain the reference for scientific validation.",
                checks=["Compare denoised and raw slices to ensure genuine structures are preserved."],
                risks=["Over-denoising can erase weak densities or create misleading visual confidence."],
                status="ready" if "tomogram" in state.detected_modalities else "conditional",
            )
        ]

    def _steps_for_ctf(self, state: DatasetState) -> list[WorkflowStep]:
        return [
            WorkflowStep(
                step_id="ctf-1",
                title="Estimate and review CTF across tilts",
                purpose="Assess defocus behavior and determine whether per-tilt or grouped correction is feasible.",
                software=["Warp"],
                inputs=["raw or motion-corrected tilt images", "tilt metadata"],
                outputs=["CTF estimates", "quality report"],
                suggested_parameters={
                    "defocus_search_range": "Keep the search range physically plausible for the acquisition setup.",
                    "per_tilt_qc": "Flag tilts with unstable fits instead of forcing every tilt into the same quality band.",
                },
                rationale="CTF correction in CryoET is metadata-sensitive, so review of fit quality matters more than blind automation.",
                checks=["Identify low-SNR or high-tilt images where CTF estimation becomes unreliable."],
                risks=["Incorrect CTF fits can degrade rather than improve the reconstructed volume."],
                status="conditional" if state.missing_requirements else "ready",
            )
        ]

    def _steps_for_missing_wedge(self, state: DatasetState) -> list[WorkflowStep]:
        return [
            WorkflowStep(
                step_id="mw-1",
                title="Plan missing wedge handling at the analysis stage",
                purpose="Choose compensation methods appropriate for downstream interpretation or subtomogram refinement.",
                software=["Dynamo", "RELION", "task-specific analysis tools"],
                inputs=["tomogram or subtomogram stack"],
                outputs=["analysis strategy that accounts for anisotropic sampling"],
                suggested_parameters={
                    "masking_strategy": "Use masks and angular coverage-aware refinement rather than pretending the wedge is absent.",
                    "comparison_mode": "Compare compensated and uncompensated results for interpretability.",
                },
                rationale="Missing wedge compensation is usually tied to downstream analysis rather than a single upstream reconstruction flag.",
                checks=["Confirm angular coverage and acquisition range before choosing the compensation approach."],
                risks=["Overstating compensation can lead to false structural confidence."],
                status="ready" if "tomogram" in state.detected_modalities else "conditional",
            )
        ]

    def _steps_for_sta(self, state: DatasetState) -> list[WorkflowStep]:
        steps = []
        if "tomogram" not in state.detected_modalities:
            steps.append(
                WorkflowStep(
                    step_id="sta-0",
                    title="Produce validated tomograms before STA",
                    purpose="STA begins from reconstructed volumes, not raw tilt images alone.",
                    software=["AreTomo", "IMOD"],
                    inputs=["tilt series or raw movies"],
                    outputs=["tomograms"],
                    suggested_parameters={},
                    rationale="Reliable subtomogram averaging depends on upstream reconstruction quality.",
                    checks=["Finish reconstruction QC before particle extraction."],
                    risks=["Low-quality tomograms will limit all later refinement gains."],
                    status="conditional",
                )
            )
        steps.extend(
            [
                WorkflowStep(
                    step_id="sta-1",
                    title="Pick particles and extract subtomograms",
                    purpose="Convert candidate particle locations into standardized subvolumes for alignment.",
                    software=["Warp", "RELION", "Dynamo"],
                    inputs=["tomograms", "particle coordinates"],
                    outputs=["subtomogram stack"],
                    suggested_parameters={
                        "box_size": "Choose a box large enough for the particle and surrounding context.",
                        "binning": "Start with binned subtomograms for early alignment and classification.",
                    },
                    rationale="Extraction is the bridge between tomogram interpretation and STA refinement.",
                    checks=["Review coordinate quality before large-scale extraction."],
                    risks=["Poor coordinates and box size choices reduce alignment convergence."],
                    status="ready" if "tomogram" in state.detected_modalities else "conditional",
                ),
                WorkflowStep(
                    step_id="sta-2",
                    title="Run initial subtomogram alignment and classification",
                    purpose="Separate good particles from junk and establish a stable starting reference.",
                    software=["RELION", "Dynamo"],
                    inputs=["subtomogram stack"],
                    outputs=["cleaned particle set", "initial averages"],
                    suggested_parameters={
                        "angular_sampling": "Start coarse and tighten only after a stable reference appears.",
                        "class_count": "Use a small number of classes initially to avoid fragmenting weak signal.",
                    },
                    rationale="A conservative first pass is usually better for beginners than aggressive high-resolution refinement.",
                    checks=["Inspect class averages for structural plausibility before further refinement."],
                    risks=["Too many classes or too fine angular steps can trap the workflow in noise."],
                    status="conditional" if "tomogram" not in state.detected_modalities else "ready",
                ),
            ]
        )
        return steps

    def _deduplicate_steps(self, steps: list[WorkflowStep]) -> list[WorkflowStep]:
        unique: list[WorkflowStep] = []
        seen = set()
        for step in steps:
            if step.step_id in seen:
                continue
            seen.add(step.step_id)
            unique.append(step)
        return unique

    def _unique(self, items: list[str]) -> list[str]:
        result = []
        seen = set()
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

