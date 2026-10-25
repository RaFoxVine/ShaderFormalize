import GeneratedModel
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

namespace ShaderFormalize.AgentProof
set_option maxHeartbeats 1000000
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops uv tint transform useTexture mode cutoff bottom
    _tintRange _useRange _modeRange _cutoffRange _bottomRange
  refine ⟨True.intro, True.intro, ?_⟩
  dsimp [Generated.original, Generated.optimized]
  by_cases hu : useTexture > (1/2 : ℝ)
  all_goals by_cases hm : mode < (1/2 : ℝ)
  all_goals by_cases hn : mode < (3/2 : ℝ)
  all_goals
    simp only [hu, hm, hn, ite_true, ite_false]
  all_goals funext x
  all_goals
    by_cases ha : ops.sample "_BaseMap" "sampler_BaseMap" [fun _ => True]
      (fun y i => uv y i * (if i.val = 0 then transform 0 else transform 1) +
        (if i.val = 0 then transform 2 else transform 3)) x 3 < cutoff
  all_goals by_cases hb : uv x 1 < bottom
  all_goals simp only [ShaderFormalize.Control.finish, ShaderFormalize.Fragment.finish]
  all_goals simp_all
  all_goals congr 1
  all_goals funext i
  all_goals fin_cases i <;> dsimp <;> ring
end ShaderFormalize.AgentProof
