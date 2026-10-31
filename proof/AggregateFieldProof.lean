import GeneratedModel
namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  norm_num [Generated.original, Generated.optimized]
end ShaderFormalize.AgentProof
