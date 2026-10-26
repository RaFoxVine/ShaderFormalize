import GeneratedModel

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  dsimp [Generated.original, Generated.optimized]
  norm_num [div_eq_mul_inv]
end ShaderFormalize.AgentProof
