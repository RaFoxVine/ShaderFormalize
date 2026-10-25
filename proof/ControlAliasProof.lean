import GeneratedModel

namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  intro E ops a
  refine ⟨True.intro, True.intro, ?_⟩
  rfl
end ShaderFormalize.AgentProof
