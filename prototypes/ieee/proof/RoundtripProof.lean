import GeneratedModel

namespace ShaderFormalize.AgentProof

theorem equivalent : ShaderFormalize.Generated.expected := by
  unfold ShaderFormalize.Generated.expected
  intro p
  unfold ShaderFormalize.Generated.original ShaderFormalize.Generated.optimized
  funext i
  fin_cases i <;> simp [ShaderIeee.Model.asfloat_asuint]

end ShaderFormalize.AgentProof
