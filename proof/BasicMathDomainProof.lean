import GeneratedModel

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  have nonnegative (x : E) (h : 0 < a x 0) : 0 ≤ a x 0 := le_of_lt h
  have square_root_nonzero (x : E) (h : 0 < a x 0) : Real.sqrt (a x 0) ≠ 0 :=
    ne_of_gt (Real.sqrt_pos.2 h)
  dsimp [Generated.original, Generated.optimized]
  simp only [if_true, true_implies, and_true, true_and]
  aesop
end ShaderFormalize.AgentProof
