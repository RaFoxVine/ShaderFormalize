import GeneratedModel

namespace ShaderFormalize.AgentProof

theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  refine ⟨True.intro, True.intro, ?_⟩
  rfl

end ShaderFormalize.AgentProof
