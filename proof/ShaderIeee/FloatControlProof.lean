import ShaderIeee.GeneratedModel

namespace ShaderIeee.AgentProof

theorem equivalent : ShaderIeee.Generated.expected := by
  unfold ShaderIeee.Generated.expected
  intro input
  funext i
  fin_cases i <;> dsimp only [Generated.original, Generated.optimized]
  all_goals try simp only [Model.asfloat_asuint]
  all_goals first | rfl | (split_ifs <;> simp_all)

end ShaderIeee.AgentProof
