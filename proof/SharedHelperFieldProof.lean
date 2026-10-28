import GeneratedModel
namespace ShaderFormalize.AgentProof

theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  dsimp (config := { instances := true }) [Generated.original, Generated.optimized, Generated.original_helper0]
  simp only [and_true, true_and, ite_true]

end ShaderFormalize.AgentProof
