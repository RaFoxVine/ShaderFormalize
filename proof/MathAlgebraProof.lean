import GeneratedModel

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a b
  dsimp (config := { instances := true }) [Generated.original, Generated.optimized, Generated.original_helper0]
  simp only [ite_true, true_and, and_true, lt_self_iff_false, ite_false]
end ShaderFormalize.AgentProof
