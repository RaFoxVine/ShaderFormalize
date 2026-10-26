import GeneratedModel
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops tint height
  have positive (x : E) : 0 < max (height x) 0 + 1 :=
    add_pos_of_nonneg_of_pos (le_max_right _ _) zero_lt_one
  have nonnegative (x : E) : 0 ≤ max (height x) 0 + 1 := le_of_lt (positive x)
  have denominator_nonzero (x : E) : Real.sqrt (max (height x) 0 + 1) + 1 ≠ 0 :=
    ne_of_gt (add_pos_of_nonneg_of_pos (Real.sqrt_nonneg _) zero_lt_one)
  have square_root_nonzero (x : E) : Real.sqrt (max (height x) 0 + 1) ≠ 0 :=
    ne_of_gt (Real.sqrt_pos.2 (positive x))
  dsimp [Generated.original, Generated.optimized,
    Generated.original_helper0, Generated.optimized_helper0]
  norm_num [positive, nonnegative, denominator_nonzero, square_root_nonzero, div_eq_mul_inv]
end ShaderFormalize.AgentProof
