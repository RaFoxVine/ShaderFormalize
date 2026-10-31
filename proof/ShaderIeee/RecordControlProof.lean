import ShaderIeee.GeneratedModel

namespace ShaderIeee.AgentProof

theorem equivalent : ShaderIeee.Generated.expected := by
  unfold ShaderIeee.Generated.expected
  intro input
  cases hlow : decide (Model.asuint (input 0) < (2147483648 : UInt32)) <;>
    cases hnan : Model.compareNotEqual (input 3) (input 3) <;>
    funext i <;>
    simp [Generated.original, Generated.optimized, hlow, hnan]

end ShaderIeee.AgentProof
