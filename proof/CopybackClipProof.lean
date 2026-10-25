import GeneratedModel
namespace ShaderFormalize.AgentProof

theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  simp [Generated.original, Generated.optimized, Generated.original_helper0,
    ShaderFormalize.Control.finish, ShaderFormalize.Fragment.finish]

end ShaderFormalize.AgentProof
