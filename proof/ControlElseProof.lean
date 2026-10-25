import GeneratedModel
import Mathlib.Tactic.Linarith

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  refine ⟨True.intro, True.intro, ?_⟩
  simp only [Generated.original, Generated.optimized]
  funext x
  by_cases hx : (a x ⟨0, by decide⟩) > (1/2 : ℝ)
  all_goals by_cases hy : (0 : ℝ) ≤ a x 1
  all_goals simp_all [ShaderFormalize.Control.finish, ShaderFormalize.Fragment.finish]
  all_goals split_ifs <;> simp_all <;> linarith
end ShaderFormalize.AgentProof
