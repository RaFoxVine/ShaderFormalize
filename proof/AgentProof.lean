import GeneratedModel

namespace ShaderFormalize.AgentProof

-- This is the agent-authored proof. GeneratedModel is rebuilt from the HLSL inputs.
theorem equivalent : ShaderFormalize.Generated.expected := by
  intro a b t hlo hhi
  funext i
  change Model.lerp (a i) (b i) (Model.saturate t) = a i + (b i - a i) * t
  rw [Model.saturate_of_range t hlo hhi]
  rfl

end ShaderFormalize.AgentProof
