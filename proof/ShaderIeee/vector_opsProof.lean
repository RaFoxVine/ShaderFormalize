import ShaderIeee.GeneratedModel
namespace ShaderIeee.AgentProof
 theorem equivalent : ShaderIeee.Generated.expected := by
  unfold ShaderIeee.Generated.expected
  intro input
  funext i
  fin_cases i <;> simp [Generated.original, Generated.optimized]
end ShaderIeee.AgentProof
