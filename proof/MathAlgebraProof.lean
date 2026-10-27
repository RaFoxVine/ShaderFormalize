import GeneratedModel

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a b
  dsimp [Generated.original, Generated.optimized, Generated.original_helper0]
  simp only [if_true, and_true, lt_self_iff_false, if_false]
end ShaderFormalize.AgentProof
