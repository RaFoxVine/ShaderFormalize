import GeneratedModel
import Mathlib.Tactic.FinCases

namespace ShaderFormalize.AgentProof
open ShaderFormalize

private theorem quantize_domain (x : ℝ) :
    0 ≤ Model.saturate x * 255 ∧ Model.saturate x * 255 < 4294967296 := by
  have low : (0 : ℝ) ≤ Model.saturate x := le_min (by norm_num) (le_max_left _ _)
  have high : Model.saturate x ≤ (1 : ℝ) := min_le_left _ _
  refine ⟨mul_nonneg low (by norm_num), ?_⟩
  calc
    Model.saturate x * 255 ≤ 1 * 255 := mul_le_mul_of_nonneg_right high (by norm_num)
    _ < 4294967296 := by norm_num

theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops color
  refine ⟨?_, ?_, ?_⟩
  · simpa [Generated.original] using
      And.intro (fun x : E => quantize_domain (color x 0))
        (fun x : E => quantize_domain (color x 1))
  · simpa [Generated.optimized] using
      And.intro (fun x : E => quantize_domain (color x 0))
        (fun x : E => quantize_domain (color x 1))
  · dsimp [Generated.original, Generated.optimized]
    apply congrArg (Control.finish (fun _ : E => True))
    funext x i
    fin_cases i
    · exact congrArg (fun n : BitVec 32 => (n.toNat : ℝ) * (1 / 256))
        (Packing.unpack_low _ _)
    · exact congrArg (fun n : BitVec 32 => (n.toNat : ℝ) * (1 / 256))
        (Packing.unpack_high _ _)
    · rfl
    · rfl

end ShaderFormalize.AgentProof
