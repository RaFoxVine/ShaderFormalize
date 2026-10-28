import GeneratedModel

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  dsimp (config := { instances := true }) [Generated.original, Generated.optimized, Generated.original_helper0]
  norm_num [ShaderFormalize.Model.saturate, div_eq_mul_inv]
end ShaderFormalize.AgentProof
