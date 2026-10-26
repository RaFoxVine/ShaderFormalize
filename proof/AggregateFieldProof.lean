import GeneratedModel
namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by
  classical
  intro E ops a
  norm_num [Generated.original, Generated.optimized]
  exact ⟨fun _ _ => by decide, fun _ => by decide⟩
end ShaderFormalize.AgentProof
