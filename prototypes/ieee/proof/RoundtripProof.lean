import ShaderIeee.GeneratedModel

namespace ShaderIeee.AgentProof

theorem equivalent : ShaderIeee.Generated.expected := by
  unfold ShaderIeee.Generated.expected
  intro p
  unfold ShaderIeee.Generated.original ShaderIeee.Generated.optimized
  funext i
  fin_cases i <;> simp [ShaderIeee.Model.asfloat_asuint]

end ShaderIeee.AgentProof
